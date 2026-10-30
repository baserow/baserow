import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync
from pydantic_ai import ToolReturn

from baserow.contrib.agent.registries import AgentToolType, agent_tool_type_registry
from baserow.core.models import Agent
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

PRESENTATIONS = {
    case["name"]: case
    for case in json.loads(
        (
            Path(__file__).resolve().parents[5] / "tests/cases/agent_tools.json"
        ).read_text()
    )["tools"]
}


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
@pytest.mark.parametrize("name", TOOLS)
def test_every_tool_acts_as_the_agent_identity(workspace_data, name):
    _, arguments = TOOLS[name]
    result = call_tool(
        agent_tool_type_registry.get(name),
        workspace_data.ctx,
        arguments(workspace_data),
    )

    assert isinstance(result, ToolReturn), result
    if name == "delete_fields":
        assert result.metadata == {"count": 0}
        assert result.return_value["deleted_field_ids"] == []
        assert "TrashEntry.user_who_trashed" in result.return_value["errors"][0]
    else:
        assert result.metadata == PRESENTATIONS[name]["facts"], result.return_value


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
def test_tool_errors_are_answered_to_the_model(workspace_data, data_fixture):
    def broken(ctx: ToolContext) -> None:
        raise RuntimeError("Private details")

    class BrokenAgentToolType(AgentToolType):
        type = "broken"
        function = broken

    other_table = data_fixture.create_database_table()

    assert call_tool(
        agent_tool_type_registry.get("list_table_rows"),
        workspace_data.ctx,
        {"table_id": other_table.id},
    ) == {"error": "Not found in this workspace."}
    assert call_tool(BrokenAgentToolType(), workspace_data.ctx, {}) == {
        "error": "Internal error."
    }
    hidden_schema = call_tool(
        agent_tool_type_registry.get("get_table_schema"),
        workspace_data.ctx,
        {"table_ids": [other_table.id]},
    )
    assert (hidden_schema.return_value, hidden_schema.metadata) == ([], {})


@pytest.mark.django_db
def test_display_facts_failure_keeps_the_successful_tool_result(workspace_data, logs):
    def done(ctx: ToolContext) -> str:
        return "Done"

    class FactlessAgentToolType(AgentToolType):
        type = "factless"
        function = done

        def get_step_facts(self, ctx, arguments, result):
            raise RuntimeError("Private details")

    result = call_tool(FactlessAgentToolType(), workspace_data.ctx, {})

    assert (result.return_value, result.metadata) == ("Done", {})
    assert [log.record["message"] for log in logs] == [
        "Agent tool factless step facts failed"
    ]


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
