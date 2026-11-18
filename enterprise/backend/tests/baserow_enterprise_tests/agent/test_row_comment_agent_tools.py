import pytest
from asgiref.sync import async_to_sync
from baserow_premium_tests.row_comments.utils import create_comment_scenario
from pydantic_ai import ToolReturn

from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.core.chat_runs.steps import ToolCallInputEvent
from baserow.core.tools import ToolContext


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
