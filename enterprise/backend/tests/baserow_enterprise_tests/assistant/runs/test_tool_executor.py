import asyncio
import threading

from django.db import DEFAULT_DB_ALIAS, connections

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai.tool_manager import ToolManager
from pydantic_ai.toolsets import FunctionToolset

from baserow_enterprise.assistant.tool_executor import ShieldedToolset, ToolExecutor


@pytest.mark.asyncio
async def test_drain_refuses_new_work_and_waits_for_the_running_call():
    executor = ToolExecutor()
    release = threading.Event()
    executor.submit(release.wait, 5)

    drained = executor.drain()

    with pytest.raises(asyncio.CancelledError):
        executor.submit(lambda: "late")
    with pytest.raises(asyncio.CancelledError):
        executor.start_tool_call(asyncio.sleep(0))
    assert not drained.done()
    release.set()
    assert await drained == [True]


@pytest.mark.asyncio
async def test_a_cancelled_agent_returns_at_once_while_its_tool_is_drained():
    executor = ToolExecutor()
    started, release = threading.Event(), threading.Event()
    seen: dict[str, object] = {}

    def slow_tool() -> str:
        """Waits until the test releases it."""

        started.set()
        release.wait(5)
        seen["finished"] = True
        return "done"

    async def stream(messages, info):
        yield {0: DeltaToolCall(name="slow_tool", json_args="{}", tool_call_id="1")}

    agent = Agent(FunctionModel(stream_function=stream))
    toolset = ShieldedToolset(FunctionToolset([slow_tool]), executor)

    async def run_agent() -> None:
        with (
            Agent.using_thread_executor(executor),
            ToolManager.parallel_execution_mode("sequential"),
        ):
            async with agent.run_stream_events("Go", toolsets=[toolset]) as events:
                async for _ in events:
                    pass

    agent_task = asyncio.create_task(run_agent())
    assert await asyncio.to_thread(started.wait, 5)
    agent_task.cancel()
    await asyncio.gather(agent_task, return_exceptions=True)

    assert "finished" not in seen
    release.set()
    await executor.drain()
    assert seen == {"finished": True}


@pytest.mark.django_db
def test_each_thread_call_closes_its_database_connection():
    executor = ToolExecutor()

    def connect():
        connection = connections[DEFAULT_DB_ALIAS]
        connection.ensure_connection()
        return connection

    thread_connection = executor.submit(connect).result(timeout=5)
    executor.shutdown()

    assert thread_connection.connection is None
