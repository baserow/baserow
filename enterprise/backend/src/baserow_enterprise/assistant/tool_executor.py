import asyncio
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, TypeVar

from django.db import connections

from pydantic_ai import RunContext
from pydantic_ai.toolsets import ToolsetTool, WrapperToolset

_R = TypeVar("_R")


def _call_and_close_connections(fn: Callable[..., _R], *args: Any, **kwargs: Any) -> _R:
    """
    Calls a function in a pool thread, then closes the thread's database
    connections, which would otherwise stay open while the thread idles.

    :param fn: The function to call.
    :return: What the function returned.
    """

    try:
        return fn(*args, **kwargs)
    finally:
        connections.close_all()


class ToolExecutor(ThreadPoolExecutor):
    """
    The thread pool of an agent answering one message. It keeps every call it
    runs and every shielded tool call, so an agent that stops can wait for the
    tools it started instead of abandoning one that may still write.
    """

    def __init__(self) -> None:
        """
        Creates an empty pool that accepts work until it drains.
        """

        super().__init__(thread_name_prefix="chat-run-tool")
        self._lock = threading.Lock()
        self._futures: list[Future] = []
        self._tool_calls: list[asyncio.Task] = []
        self._draining = False

    def submit(self, fn: Callable[..., _R], /, *args: Any, **kwargs: Any) -> Future[_R]:
        """
        Runs a function in a pool thread. pydantic-ai hands sync tools over
        already wrapped in a copy of the caller's context.

        :param fn: The function to run.
        :return: The future of the call.
        :raises asyncio.CancelledError: When the drain began, so no work starts
            after a stop.
        """

        with self._lock:
            if self._draining:
                raise asyncio.CancelledError()
            future = super().submit(_call_and_close_connections, fn, *args, **kwargs)
            self._futures.append(future)
            return future

    def start_tool_call(self, call: Coroutine[Any, Any, _R]) -> asyncio.Task[_R]:
        """
        Runs a tool call as a task of its own, which cancelling the agent
        doesn't interrupt.

        :param call: The tool call.
        :return: The task running it.
        :raises asyncio.CancelledError: When the drain began.
        """

        with self._lock:
            if self._draining:
                call.close()
                raise asyncio.CancelledError()
            task = asyncio.create_task(call)
            self._tool_calls.append(task)
        return task

    def drain(self) -> asyncio.Future[list[Any]]:
        """
        Starts no new work from now on, and returns a future that ends, with no
        time limit, once every call already started has ended. The future is
        shielded, so a caller that bounds it with `asyncio.wait_for` never
        cancels the tools.

        :return: The future to await.
        """

        with self._lock:
            self._draining = True
            futures = list(self._futures)
            tool_calls = list(self._tool_calls)
        self.shutdown(wait=False, cancel_futures=True)
        return asyncio.shield(
            asyncio.gather(
                *(asyncio.wrap_future(future) for future in futures),
                *tool_calls,
                return_exceptions=True,
            )
        )


@dataclass
class ShieldedToolset(WrapperToolset[Any]):
    """
    Runs every tool call through the executor, so cancelling the agent returns
    at once while the call goes on until the executor drains it.
    """

    executor: ToolExecutor

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        """
        :param name: The name of the tool.
        :param tool_args: The validated arguments.
        :param ctx: The run context.
        :param tool: The tool definition.
        :return: What the tool returned.
        """

        call = self.executor.start_tool_call(
            self.wrapped.call_tool(name, tool_args, ctx, tool)
        )
        return await asyncio.shield(call)
