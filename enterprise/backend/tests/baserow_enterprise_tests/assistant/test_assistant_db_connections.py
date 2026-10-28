from django.db import connection, connections

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.toolsets import CombinedToolset, FunctionToolset

from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.database.tools import database_toolset
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry
from baserow_enterprise.assistant.tools.toolset import AssistantFunctionToolset

from .utils import make_test_ctx

tool_backend_pids: list[int] = []


def backend_pid() -> str:
    """Report the database backend of the thread running the tools."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        tool_backend_pids.append(cursor.fetchone()[0])
    return "ok"


def _list_tables_report_pid_then_answer(
    messages: list[ModelMessage], info: AgentInfo
) -> ModelResponse:
    tool_returns = [
        part
        for message in messages
        for part in message.parts
        if part.part_kind == "tool-return"
    ]
    if not tool_returns:
        return ModelResponse(
            parts=[ToolCallPart("list_tables", {"filters": {}, "thought": "List"})]
        )
    if len(tool_returns) == 1:
        return ModelResponse(parts=[ToolCallPart("backend_pid", {})])
    return ModelResponse(parts=[TextPart(str(tool_returns[0].content))])


def _terminate_backend(pid: int):
    """Drop one database session, as a Postgres restart would."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_terminate_backend(%s)", [pid])


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("conn_max_age", [0, None])
def test_tools_reconnect_after_the_database_drops_their_connection(
    data_fixture, monkeypatch, conn_max_age
):
    # With persistent connections the tool thread keeps its connection between
    # runs instead of opening a new one per call.
    monkeypatch.setitem(connections.settings["default"], "CONN_MAX_AGE", conn_max_age)
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    data_fixture.create_database_table(database=database, name="Customers")
    deps = make_test_ctx(user, workspace).deps
    tool_backend_pids.clear()
    agent = Agent(
        FunctionModel(_list_tables_report_pid_then_answer),
        deps_type=AssistantDeps,
        # backend_pid does not refresh the connection, so list_tables, the first
        # call after the restart, has to do it itself.
        toolsets=[CombinedToolset([database_toolset, FunctionToolset([backend_pid])])],
    )

    async def run_twice_with_a_database_restart_in_between():
        # One event loop for both runs, so the second run's tool calls land on
        # the worker thread that ran the first one.
        first = await agent.run("List the tables", deps=deps)
        await sync_to_async(_terminate_backend)(tool_backend_pids[0])
        second = await agent.run("List the tables again", deps=deps)
        return first.output, second.output

    first, second = async_to_sync(run_twice_with_a_database_restart_in_between)()

    assert "Customers" in first
    assert "Customers" in second


def test_every_assistant_toolset_refreshes_db_connections():
    for tool_type in assistant_tool_registry.get_all():
        assert isinstance(tool_type.get_toolset(), AssistantFunctionToolset), (
            tool_type.type
        )


def _toolsets_with_tools(toolsets) -> list:
    return [ts for ts in toolsets if not isinstance(ts, FunctionToolset) or ts.tools]


@pytest.mark.django_db
def test_dynamic_toolset_refreshes_db_connections(data_fixture):
    from pydantic_ai import Tool

    from baserow_enterprise.assistant.agents import dynamic_toolset

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)
    ctx.deps.dynamic_tools.append(Tool(lambda: "ok", name="row_tool"))

    assert isinstance(dynamic_toolset(ctx), AssistantFunctionToolset)


@pytest.mark.django_db
def test_nested_agent_toolsets_refresh_db_connections(data_fixture, monkeypatch):
    from baserow_enterprise.assistant.tools.database import agents as database_agents

    from .utils import create_fake_tool_helpers

    toolsets = []

    def record_run(agent, prompt, **kwargs):
        toolsets.extend(_toolsets_with_tools(agent.toolsets))
        toolsets.extend(_toolsets_with_tools(kwargs.get("toolsets", [])))

    monkeypatch.setattr(database_agents, "run_agent_sync_with_model", record_run)
    monkeypatch.setattr(
        database_agents, "get_formula_type_tool", lambda user, workspace: lambda: ""
    )
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True)
    helpers = create_fake_tool_helpers()

    database_agents.run_formula_generation(
        user, workspace, "Generate", helpers.model_profile
    )
    database_agents.generate_sample_rows(user, workspace, helpers, [table])

    assert len(toolsets) == 2
    for toolset in toolsets:
        assert isinstance(toolset, AssistantFunctionToolset)
