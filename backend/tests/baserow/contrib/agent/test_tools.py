import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import OperationalError
from django.urls import reverse

import pytest
from asgiref.sync import async_to_sync
from freezegun import freeze_time
from pydantic import ValidationError
from pydantic_ai import ToolReturn
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.agent.registries import AgentToolType, agent_tool_type_registry
from baserow.contrib.database.views.models import FormView
from baserow.core.chat_runs.constants import ChatRunStepErrorCode
from baserow.core.exceptions import (
    InstanceTypeDoesNotExist,
    PermissionDenied,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.mcp.exceptions import MCPToolInputError
from baserow.core.models import Agent
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.tools import ToolContext

# Whether each tool changes data, and arguments it succeeds with on workspace_data.
TOOLS = {
    "list_tables": (False, lambda s: {}),
    "get_table_schema": (False, lambda s: {"table_ids": [s.table.id]}),
    "list_table_rows": (False, lambda s: {"table_id": s.table.id}),
    "list_views": (False, lambda s: {"table_id": s.table.id}),
    "create_tables": (
        True,
        lambda s: {
            "database_id": s.table.database_id,
            "tables": [
                {"name": "Projects", "primary_field_name": "Title", "fields": []}
            ],
        },
    ),
    "create_fields": (
        True,
        lambda s: {
            "table_id": s.table.id,
            "fields": [{"name": "Notes", "type": "text"}],
        },
    ),
    "update_fields": (
        True,
        lambda s: {"fields": [{"field_id": s.hours.id, "name": "Effort"}]},
    ),
    "delete_fields": (True, lambda s: {"field_ids": [s.hours.id]}),
    "create_views": (
        True,
        lambda s: {
            "table_id": s.table.id,
            "views": [{"name": "Board", "type": "grid"}],
        },
    ),
    "create_view_filters": (
        True,
        lambda s: {
            "view_filters": [
                {
                    "view_id": s.view.id,
                    "filters": [
                        {
                            "field_id": s.hours.id,
                            "type": "number",
                            "operator": "higher_than",
                            "value": 1,
                        }
                    ],
                }
            ]
        },
    ),
    "create_rows": (
        True,
        lambda s: {"table_id": s.table.id, "rows": [{"Name": "Plan"}]},
    ),
    "update_rows": (
        True,
        lambda s: {
            "table_id": s.table.id,
            "rows": [{"id": s.row.id, "Name": "Done"}],
        },
    ),
    "delete_rows": (True, lambda s: {"table_id": s.table.id, "row_ids": [s.row.id]}),
}

PRESENTATION_CONTRACT = json.loads(
    (Path(__file__).resolve().parents[5] / "tests/cases/agent_tools.json").read_text()
)
PRESENTATIONS = {case["name"]: case for case in PRESENTATION_CONTRACT["tools"]}


@pytest.fixture
def workspace_data(data_fixture):
    """A table of a workspace, and an Agent identity of that workspace to act as."""

    table = data_fixture.create_database_table(name="Tasks")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    workspace = table.database.workspace
    identity = Agent.objects.create(workspace=workspace, name="Ops")
    return SimpleNamespace(
        ctx=ToolContext(user=identity, workspace=workspace),
        table=table,
        hours=data_fixture.create_number_field(table=table, name="Hours"),
        view=data_fixture.create_grid_view(table=table),
        row=table.get_model().objects.create(),
    )


def call_tool(tool_type: AgentToolType, ctx: ToolContext, arguments: dict) -> object:
    tool = tool_type.get_tool(ctx)
    return async_to_sync(tool.function)(
        **tool.function_schema.validator.validate_python(arguments)
    )


def test_tool_names_and_whether_they_change_data_stay_the_same():
    """
    Agents allow tools by name: a rename drops a tool, a reused name allows the new
    tool, and a read tool that starts changing data does so where only reads were
    allowed. Change this only with a migration of the allowed tools.
    """

    assert {
        tool_type.type: tool_type.changes_data
        for tool_type in agent_tool_type_registry.get_all()
    } == {name: changes_data for name, (changes_data, _) in TOOLS.items()}
    assert set(PRESENTATIONS) == set(TOOLS)
    assert list(ChatRunStepErrorCode) == PRESENTATION_CONTRACT["step_error_codes"]


@pytest.mark.parametrize("name", PRESENTATIONS)
def test_tool_presentation_contract_uses_valid_arguments_and_safe_summaries(name):
    case = PRESENTATIONS[name]
    tool_type = agent_tool_type_registry.get(name)
    tool_type.get_tool(None).function_schema.validator.validate_python(
        case["arguments"]
    )

    assert tool_type.presentation_type == case["presentation_type"]
    assert tool_type.get_step_input(case["arguments"]) == case["input"]
    assert tool_type.get_step_input({}) == {}
    assert (
        tool_type.get_step_input({key: "private value" for key in case["arguments"]})
        == {}
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason="Agent trash/user attribution requires the broader fix in #6259",
            ),
        )
        if name == "delete_fields"
        else name
        for name in TOOLS
    ],
)
def test_every_tool_acts_as_the_agent_identity(workspace_data, name):
    _, arguments = TOOLS[name]
    result = call_tool(
        agent_tool_type_registry.get(name),
        workspace_data.ctx,
        arguments(workspace_data),
    )

    assert isinstance(result, ToolReturn), result
    value = result.return_value
    if name == "delete_fields":
        workspace_data.hours.refresh_from_db()
        assert workspace_data.hours.trashed
        assert value["deleted_field_ids"] == [workspace_data.hours.id]
    assert not (
        isinstance(value, dict) and (value.get("error") or value.get("errors"))
    ), value
    assert result.metadata == PRESENTATIONS[name]["facts"], value


@pytest.mark.django_db
def test_successful_field_deletion_reports_its_confirmed_count(
    workspace_data, data_fixture
):
    ctx = ToolContext(
        user=data_fixture.create_user(workspace=workspace_data.ctx.workspace),
        workspace=workspace_data.ctx.workspace,
    )
    result = call_tool(
        agent_tool_type_registry.get("delete_fields"),
        ctx,
        {"field_ids": [workspace_data.hours.id]},
    )

    assert result.metadata == PRESENTATIONS["delete_fields"]["facts"]
    assert result.return_value == {"deleted_field_ids": [workspace_data.hours.id]}


@pytest.mark.django_db
def test_agent_form_creation_does_not_notify_user_with_same_id(
    data_fixture, api_client
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    workspace = table.database.workspace
    identity = Agent.objects.create(id=user.id, workspace=workspace, name="Ops")

    result = call_tool(
        agent_tool_type_registry.get("create_views"),
        ToolContext(user=identity, workspace=workspace),
        {
            "table_id": table.id,
            "views": [
                {
                    "name": "Contact form",
                    "type": "form",
                    "public": True,
                    "receive_notification_on_submit": True,
                    "field_options": [
                        {
                            "field_id": field.id,
                            "name": "Name",
                            "description": "",
                            "required": False,
                            "order": 1,
                        }
                    ],
                }
            ],
        },
    )

    assert "error" not in result.return_value
    form = FormView.objects.get(id=result.return_value["created_views"][0]["id"])
    response = api_client.post(
        reverse("api:database:views:form:submit", kwargs={"slug": form.slug}),
        {field.db_column: "Submitted name"},
        format="json",
    )

    assert response.status_code == 200
    assert not NotificationRecipient.objects.filter(
        recipient=user, notification__type="form_submitted"
    ).exists()
    assert not form.users_to_notify_on_submit.exists()


@pytest.mark.django_db
def test_tool_errors_are_answered_to_the_model(workspace_data, data_fixture):
    def broken(ctx: ToolContext) -> None:
        raise RuntimeError("Private details")

    class BrokenAgentToolType(AgentToolType):
        type = "broken"
        function = broken

    other_table = data_fixture.create_database_table()

    missing = call_tool(
        agent_tool_type_registry.get("list_table_rows"),
        workspace_data.ctx,
        {"table_id": other_table.id},
    )
    assert missing.return_value == {"error": "Not found in this workspace."}
    assert missing.metadata == {"error_code": "not_found"}
    unexpected = call_tool(BrokenAgentToolType(), workspace_data.ctx, {})
    assert unexpected.return_value == {"error": "Internal error."}
    assert unexpected.metadata == {"error_code": "failed"}
    hidden_schema = call_tool(
        agent_tool_type_registry.get("get_table_schema"),
        workspace_data.ctx,
        {"table_ids": [other_table.id]},
    )
    assert (hidden_schema.return_value, hidden_schema.metadata) == ([], {})


@pytest.mark.django_db
def test_display_facts_failure_keeps_the_successful_tool_result(workspace_data, logs):
    private_argument = "PRIVATE_FACTS_ARGUMENT_CANARY"
    private_result = "PRIVATE_FACTS_RESULT_CANARY"
    private_error = "PRIVATE_FACTS_ERROR_CANARY"

    def done(ctx: ToolContext, private_value: str) -> str:
        return private_result

    class FactlessAgentToolType(AgentToolType):
        type = "factless"
        function = done

        def get_step_facts(self, ctx, arguments, result):
            raise RuntimeError(private_error)

    result = call_tool(
        FactlessAgentToolType(),
        workspace_data.ctx,
        {"private_value": private_argument},
    )

    assert (result.return_value, result.metadata) == (private_result, {})
    assert [log.record["message"] for log in logs] == [
        "Agent tool factless step facts failed (RuntimeError)"
    ]
    output = "".join(str(entry) for entry in logs)
    assert private_argument not in output
    assert private_result not in output
    assert private_error not in output


@pytest.mark.django_db
def test_returned_errors_never_extract_display_facts(workspace_data, mocker):
    def refused(ctx: ToolContext) -> dict:
        return {"error": "Not allowed"}

    class RefusedAgentToolType(AgentToolType):
        type = "refused"
        function = refused

    tool_type = RefusedAgentToolType()
    facts = mocker.patch.object(tool_type, "get_step_facts")

    assert call_tool(tool_type, workspace_data.ctx, {}) == {"error": "Not allowed"}
    facts.assert_not_called()


@pytest.mark.django_db
def test_reused_tables_do_not_count_as_created(workspace_data):
    result = call_tool(
        agent_tool_type_registry.get("create_tables"),
        workspace_data.ctx,
        {
            "database_id": workspace_data.table.database_id,
            "tables": [{"name": "Tasks", "primary_field_name": "Name", "fields": []}],
        },
    )

    assert result.metadata == {"count": 0}
    assert result.return_value["created_tables"] == []


@pytest.mark.django_db
def test_partial_field_creation_counts_only_created_fields(workspace_data):
    tool_type = agent_tool_type_registry.get("create_fields")
    arguments = {
        "table_id": workspace_data.table.id,
        "fields": [
            {"name": "Notes", "type": "text"},
            {"name": "Broken", "type": "formula", "formula": "unknown("},
        ],
    }

    result = call_tool(tool_type, workspace_data.ctx, arguments)

    assert tool_type.get_step_input(arguments) == {"requested_count": 2}
    assert result.metadata == {"table": "Tasks", "count": 1}
    assert len(result.return_value["formula_errors"]) == 1


@pytest.mark.django_db
def test_tool_calls_track_identity_usage_with_the_existing_throttle(workspace_data):
    identity = workspace_data.ctx.user
    assert identity.last_active is None

    with freeze_time() as clock:
        result = call_tool(
            agent_tool_type_registry.get("list_views"),
            workspace_data.ctx,
            {"table_id": workspace_data.table.id},
        )
        assert "error" not in result.return_value
        identity.refresh_from_db()
        first_activity = identity.last_active
        assert first_activity is not None

        clock.tick(30)
        result = call_tool(
            agent_tool_type_registry.get("list_views"),
            workspace_data.ctx,
            {"table_id": workspace_data.table.id},
        )
        assert "error" not in result.return_value
        identity.refresh_from_db()
        assert identity.last_active == first_activity


@pytest.mark.django_db
def test_unexpected_tool_errors_do_not_log_private_values(workspace_data, mocker, logs):
    private_search = "PRIVATE_SEARCH_CANARY"
    private_error = "PRIVATE_ERROR_CANARY"
    mocker.patch(
        "baserow.contrib.database.tools.rows.serialize_rows_for_response",
        side_effect=OperationalError(private_error),
    )

    result = call_tool(
        agent_tool_type_registry.get("list_table_rows"),
        workspace_data.ctx,
        {"table_id": workspace_data.table.id, "search": private_search},
    )

    assert result.return_value == {"error": "Internal error."}
    assert result.metadata == {"error_code": "failed"}
    output = "".join(str(entry) for entry in logs)
    assert "list_table_rows" in output
    assert "OperationalError" in output
    assert private_search not in output
    assert private_error not in output


@pytest.mark.django_db
def test_a_stop_waits_for_the_running_tool(workspace_data):
    started, release = threading.Event(), threading.Event()

    def slow(ctx: ToolContext) -> str:
        started.set()
        release.wait(5)
        return "Changed"

    class SlowAgentToolType(AgentToolType):
        type = "slow"
        function = slow

    async def stop_during_the_call() -> bool:
        call = asyncio.ensure_future(
            SlowAgentToolType().get_tool(workspace_data.ctx).function()
        )
        await asyncio.to_thread(started.wait, 5)
        call.cancel()
        await asyncio.sleep(0.1)
        still_running = not call.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await call
        return still_running

    assert async_to_sync(stop_during_the_call)()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error,code",
    [
        (ObjectDoesNotExist("private details"), "not_found"),
        (WorkspaceDoesNotExist("private details"), "not_found"),
        (UserNotInWorkspace(), "not_found"),
        (PermissionDenied(), "permission_denied"),
        (DRFPermissionDenied("private details"), "permission_denied"),
        (DjangoValidationError("private details"), "invalid_input"),
        (DRFValidationError({"field": "private details"}), "invalid_input"),
        (RequestBodyValidationException({"field": "private details"}), "invalid_input"),
        (MCPToolInputError("private details"), "invalid_input"),
        (InstanceTypeDoesNotExist("bad_type", "unknown type"), "invalid_input"),
        (InstanceTypeDoesNotExist("model not registered"), "failed"),
        (RuntimeError("Not found in this workspace."), "failed"),
        (
            ValidationError.from_exception_data(
                "Tool", [{"type": "int_parsing", "loc": ("id",), "input": "private"}]
            ),
            "invalid_input",
        ),
        (
            type("RelatedObjectDoesNotExist", (ObjectDoesNotExist, AttributeError), {})(
                "private details"
            ),
            "failed",
        ),
    ],
)
def test_tool_failure_codes_use_exception_types_without_copying_private_details(
    workspace_data, error, code
):
    def fail(ctx: ToolContext) -> None:
        raise error

    class FailingTool(AgentToolType):
        type = "failing"
        function = fail

    result = call_tool(FailingTool(), workspace_data.ctx, {})

    assert isinstance(result, ToolReturn)
    assert set(result.return_value) == {"error"}
    assert result.metadata == {"error_code": code}
