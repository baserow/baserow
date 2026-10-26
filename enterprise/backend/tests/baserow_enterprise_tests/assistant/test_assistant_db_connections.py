from django.db import connection, connections

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.toolsets import CombinedToolset

from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.database.tools import database_toolset
from baserow_enterprise.assistant.tools.toolset import AssistantFunctionToolset

from .utils import make_test_ctx

tool_backend_pids: list[int] = []


def backend_pid() -> str:
    """Report the database backend of the thread running the tools."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        tool_backend_pids.append(cursor.fetchone()[0])
    return "ok"


def _report_pid_list_tables_then_answer(
    messages: list[ModelMessage], info: AgentInfo
) -> ModelResponse:
    tool_returns = [
        part
        for message in messages
        for part in message.parts
        if part.part_kind == "tool-return"
    ]
    if not tool_returns:
        return ModelResponse(parts=[ToolCallPart("backend_pid", {})])
    if len(tool_returns) == 1:
        return ModelResponse(
            parts=[ToolCallPart("list_tables", {"filters": {}, "thought": "List"})]
        )
    return ModelResponse(parts=[TextPart(str(tool_returns[-1].content))])


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
        FunctionModel(_report_pid_list_tables_then_answer),
        deps_type=AssistantDeps,
        toolsets=[
            CombinedToolset([database_toolset, AssistantFunctionToolset([backend_pid])])
        ],
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
