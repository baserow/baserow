import asyncio
import threading
from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync

from baserow.contrib.agent.registries import AgentToolType, agent_tool_type_registry
from baserow.core.models import Agent
from baserow.core.tools import ToolContext

TOOL_ARGUMENTS = {
    "list_tables": lambda s: {},
    "get_table_schema": lambda s: {"table_ids": [s.table.id]},
    "list_table_rows": lambda s: {"table_id": s.table.id},
    "list_views": lambda s: {"table_id": s.table.id},
    "create_tables": lambda s: {
        "database_id": s.table.database_id,
        "tables": [{"name": "Projects", "primary_field_name": "Title", "fields": []}],
    },
    "create_fields": lambda s: {
        "table_id": s.table.id,
        "fields": [{"name": "Notes", "type": "text"}],
    },
    "update_fields": lambda s: {"fields": [{"field_id": s.hours.id, "name": "Effort"}]},
    "delete_fields": lambda s: {"field_ids": [s.hours.id]},
    "create_views": lambda s: {
        "table_id": s.table.id,
        "views": [{"name": "Board", "type": "grid"}],
    },
    "create_view_filters": lambda s: {
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
    "create_rows": lambda s: {"table_id": s.table.id, "rows": [{"Name": "Plan"}]},
    "update_rows": lambda s: {
        "table_id": s.table.id,
        "rows": [{"id": s.row.id, "Name": "Done"}],
    },
    "delete_rows": lambda s: {"table_id": s.table.id, "row_ids": [s.row.id]},
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


@pytest.mark.django_db
@pytest.mark.parametrize("name", agent_tool_type_registry.get_types())
def test_every_tool_acts_as_the_agent_identity(workspace_data, name):
    result = call_tool(
        agent_tool_type_registry.get(name),
        workspace_data.ctx,
        TOOL_ARGUMENTS[name](workspace_data),
    )

    assert not (isinstance(result, dict) and "error" in result), result


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
