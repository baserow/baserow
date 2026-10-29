import asyncio
import inspect
from typing import Any, Callable, get_type_hints

from asgiref.sync import sync_to_async
from loguru import logger
from pydantic_ai import Tool

from baserow.core.mcp.exceptions import INTERNAL_ERROR_MESSAGE, to_mcp_error
from baserow.core.registry import Instance, Registry
from baserow.core.tools import ToolContext


def _call_tool(
    function: Callable[..., Any], ctx: ToolContext, arguments: dict[str, Any]
) -> Any:
    """
    Run a shared tool, answering an error the model can explain instead of failing
    the reply.

    :param function: The shared tool.
    :param ctx: Who the tool acts for.
    :param arguments: The validated arguments.
    :return: What the tool returned, or an ``error`` message.
    """

    try:
        return function(ctx, **arguments)
    except Exception as exc:
        message = to_mcp_error(exc)
        if message is None:
            logger.exception("Agent tool {} failed", function.__name__)
            message = INTERNAL_ERROR_MESSAGE
        return {"error": message}


async def _run_tool(
    function: Callable[..., Any], ctx: ToolContext, arguments: dict[str, Any]
) -> Any:
    """
    Run a shared tool without blocking the reply's event loop. A stop waits for the
    running tool, so a reply never ends while its tool still changes data.

    :param function: The shared tool.
    :param ctx: Who the tool acts for.
    :param arguments: The validated arguments.
    :return: What the tool returned, or an ``error`` message.
    """

    # On the worker's own thread, so tools share its connection and never leak one.
    running = asyncio.ensure_future(sync_to_async(_call_tool)(function, ctx, arguments))
    try:
        return await asyncio.shield(running)
    except asyncio.CancelledError:
        await asyncio.wait({running})
        raise


class AgentToolType(Instance):
    """
    A tool an Agent can call: a function shared with the other clients, see
    ``baserow.core.tools``, offered under the name MCP uses for it.
    """

    function: Callable[..., Any]

    changes_data: bool = False
    """True when the tool creates, changes or deletes data. It then runs alone, and
    new Agents start without it."""

    def get_tool(self, ctx: ToolContext) -> Tool:
        """
        Build the tool for one reply, acting for the given context.

        :param ctx: Who the tool acts for, and where.
        :return: The tool, with the input schema of the shared function minus its
            context.
        """

        function = type(self).function
        hints = get_type_hints(function, include_extras=True)
        parameters = [
            parameter.replace(kind=inspect.Parameter.KEYWORD_ONLY)
            for parameter in list(inspect.signature(function).parameters.values())[1:]
        ]

        async def call(**arguments: Any) -> Any:
            return await _run_tool(function, ctx, arguments)

        call.__signature__ = inspect.Signature(parameters)
        call.__annotations__ = {
            parameter.name: hints[parameter.name] for parameter in parameters
        }
        return Tool(
            call,
            takes_ctx=False,
            name=self.type,
            description=function.__doc__,
            sequential=self.changes_data,
        )


class AgentToolTypeRegistry(Registry[AgentToolType]):
    name = "agent_tool"


agent_tool_type_registry = AgentToolTypeRegistry()
