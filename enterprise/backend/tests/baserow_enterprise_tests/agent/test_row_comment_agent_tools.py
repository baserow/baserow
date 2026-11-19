from django.urls import reverse

import pytest
from asgiref.sync import async_to_sync
from baserow_premium_tests.row_comments.utils import create_comment_scenario
from pydantic import ValidationError
from pydantic_ai import ToolReturn
from pydantic_ai.models.function import FunctionModel
from rest_framework.status import HTTP_402_PAYMENT_REQUIRED

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.replies import AgentResponder
from baserow.contrib.agent.service import AgentService
from baserow.core.chat_runs.steps import ToolCallInputEvent
from baserow.core.handler import CoreHandler
from baserow.core.tools import ToolContext
from baserow_premium.license.cache import invalidate_cached_instance_wide_licenses
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.row_comments.tools import MAX_PAGE

ROW_COMMENT_TOOLS = {
    "list_row_comments": False,
    "search_row_comments": False,
    "create_row_comments": True,
}


class ModelRun:
    """The model run a tool streams its readable request to."""

    def __init__(self) -> None:
        self.input: dict = {}

    async def emit(self, event: ToolCallInputEvent) -> None:
        self.input = event.input


def call_tool(name: str, ctx: ToolContext, arguments: dict) -> tuple[ToolReturn, dict]:
    """
    :param name: The tool to call as an Agent does.
    :param ctx: The identity it acts as.
    :param arguments: The arguments as a model sends them.
    :return: What the tool returned and the readable request it showed.
    """

    tool = agent_tool_type_registry.get(name).get_tool(ctx)
    run = ModelRun()
    result = async_to_sync(tool.function)(
        run, **tool.function_schema.validator.validate_python(arguments)
    )
    assert isinstance(result, ToolReturn), result
    return result, run.input


@pytest.mark.django_db
def test_an_identity_uses_the_row_comment_tools_with_a_workspace_licence(
    enterprise_data_fixture, synced_roles, enable_enterprise
):
    scenario = create_comment_scenario(enterprise_data_fixture)
    workspace = scenario.ctx.workspace
    identity = enterprise_data_fixture.create_identity(
        workspace=workspace, role_uid="ADMIN", name="Helper"
    )
    ctx = ToolContext(user=identity, workspace=workspace)
    row = scenario.task_rows[0]

    created, create_request = call_tool(
        "create_row_comments",
        ctx,
        {"table_id": scenario.tasks.id, "comments": [{"row_id": row.id, "text": "Ok"}]},
    )
    found, search_request = call_tool(
        "search_row_comments",
        ctx,
        {
            "database_id": scenario.database.id,
            "table_ids": [scenario.tasks.id],
            "authors": [0],
            "created_after": "2026-06-01T00:00:00Z",
        },
    )
    listed, list_request = call_tool(
        "list_row_comments", ctx, {"table_id": scenario.tasks.id, "row_id": row.id}
    )

    assert not agent_tool_type_registry.get("search_row_comments").is_deactivated(
        workspace
    )
    assert create_request["values"] == {
        "table": "Tasks",
        "comments": [{"row": "Call", "text": "Ok"}],
    }
    assert created.metadata == {"facts": {"count": 1}}
    assert search_request["values"] == {
        "database": scenario.database.name,
        "tables": ["Tasks"],
        "authors": ["Helper"],
        "created_after": "2026-06-01 00:00:00+00:00",
    }
    assert [comment["text"] for comment in found.return_value["comments"]] == ["Ok"]
    assert found.metadata == {"facts": {"count": 1}}
    assert list_request["values"] == {"table": "Tasks", "row": "Call"}
    assert listed.metadata == {"facts": {"count": 2}}

    search = agent_tool_type_registry.get("search_row_comments")
    spelled_out = {"database_id": scenario.database.id, "authors": ["0", "Bob"]}
    assert search.get_step_preview(ctx, spelled_out).to_input()["values"][
        "authors"
    ] == ["Helper", "Bob"]
    for name, arguments in (
        ("search_row_comments", {"database_id": scenario.database.id}),
        ("list_row_comments", {"table_id": scenario.tasks.id, "row_id": row.id}),
    ):
        with pytest.raises(ValidationError):
            call_tool(name, ctx, {**arguments, "page": MAX_PAGE + 1})


def test_row_comment_tool_names_and_whether_they_change_data_stay_the_same():
    """Agents allow tools by name; change this only with a migration of them."""

    assert {
        tool_type.type: tool_type.changes_data
        for tool_type in agent_tool_type_registry.get_all()
        if type(tool_type).__module__.startswith("baserow_enterprise.agent.")
    } == ROW_COMMENT_TOOLS


@pytest.mark.django_db
@pytest.mark.parametrize("has_premium_seat", [False, True])
def test_row_comment_tools_are_locked_without_a_workspace_licence(
    premium_data_fixture, api_client, settings, has_premium_seat, mocker
):
    settings.DEBUG = True
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=has_premium_seat
    )
    agent = premium_data_fixture.create_agent_application(
        user=user, provider_type="openai", model_identifier="test-model"
    )
    identity = premium_data_fixture.create_identity(workspace=agent.workspace)
    agent.run_as_subject_type, agent.run_as_subject_id = "auth.User", identity.id
    agent.save()
    assert (
        LicenseHandler.user_has_feature(PREMIUM, user, agent.workspace)
        == has_premium_seat
    )
    # Allowed while the workspace had the licence.
    AgentHandler().set_allowed_tools(agent, ["list_tables", "search_row_comments"])
    url = reverse("api:agent:configuration", kwargs={"agent_id": agent.id})
    api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")

    configuration = api_client.get(url).json()
    response = api_client.patch(
        url, {"allowed_tools": ["list_tables", "create_row_comments"]}, format="json"
    )

    assert {
        tool["name"] for tool in configuration["available_tools"] if tool["deactivated"]
    } == set(ROW_COMMENT_TOOLS)
    assert configuration["allowed_tools"] == ["list_tables"]
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"

    prompt = premium_data_fixture.create_agent_message(agent=agent, user=user)
    reply = premium_data_fixture.create_agent_message(conversation=prompt.conversation)
    request = AgentHandler().get_reply_request(reply)
    assert request.allowed_tool_names == ["list_tables"]

    async def stream(messages, info):
        assert [tool.name for tool in info.function_tools] == ["list_tables"]
        instructions = messages[-1].instructions
        assert instructions.count("Advanced") == 1
        # Only the tool the Agent was allowed is named.
        assert "search_row_comments" in instructions
        assert "create_row_comments" not in instructions
        yield "ok"

    responder = AgentResponder(
        request, mocker.Mock(), FunctionModel(stream_function=stream), {}
    )
    async_to_sync(responder._run_model)(None)

    # A running reply rechecks the licence before showing a preview or writing.
    result, preview = call_tool(
        "create_row_comments",
        ToolContext(user=identity, workspace=agent.workspace),
        {"table_id": 1, "comments": [{"row_id": 1, "text": "Example"}]},
    )
    assert "licence" in result.return_value["error"]["message"].lower()
    assert not preview

    # An Agent that was never allowed a locked tool isn't told about them.
    AgentHandler().set_allowed_tools(agent, ["list_tables"])
    assert AgentHandler().get_reply_request(reply).unavailable_tool_messages == []


@pytest.mark.django_db
def test_tool_grants_can_be_copied_and_revoked_during_a_licence_lapse(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(user=user)
    identity = enterprise_data_fixture.create_identity(workspace=agent.workspace)
    service = AgentService()
    grants = {
        "allowed_tools": ["list_row_comments", "create_row_comments"],
        "ask_first_tools": ["list_row_comments"],
    }
    service.update_configuration(
        user,
        agent.id,
        run_as_subject_type="auth.User",
        run_as_subject_id=identity.id,
        **grants,
    )
    enterprise_data_fixture.delete_all_licenses()
    invalidate_cached_instance_wide_licenses()

    edited = service.update_configuration(
        user, agent.id, instructions="New instructions"
    )
    assert edited.configuration.allowed_tools == []
    for field, expected in grants.items():
        assert edited.original_values[field] == edited.new_values[field] == expected
    duplicate = CoreHandler().duplicate_application(user, edited.agent).specific
    assert service.get_configuration(user, duplicate.id).allowed_tools == []

    cleared = service.update_configuration(user, agent.id, allowed_tools=[])
    assert cleared.original_values["allowed_tools"] == grants["allowed_tools"]
    assert cleared.new_values["allowed_tools"] == []
    enterprise_data_fixture.enable_enterprise()
    invalidate_cached_instance_wide_licenses()
    assert service.get_configuration(user, agent.id).allowed_tools == []
    assert AgentHandler().get_tool_configuration(duplicate) == grants
