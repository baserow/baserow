import asyncio
import inspect
import json
from typing import Any, Callable, get_type_hints

from asgiref.sync import sync_to_async
from loguru import logger
from pydantic_ai import Tool, ToolReturn

from baserow.core.mcp.exceptions import INTERNAL_ERROR_MESSAGE, to_mcp_error
from baserow.core.registry import Instance, Registry
from baserow.core.tools import ToolContext


def _call_tool(
    tool_type: "AgentToolType", ctx: ToolContext, arguments: dict[str, Any]
) -> Any:
    """
    Run a shared tool, answering an error the model can explain instead of failing
    the reply.

    :param tool_type: The shared tool and its presentation.
    :param ctx: Who the tool acts for.
    :param arguments: The validated arguments.
    :return: What the tool returned, or an ``error`` message.
    """

    function = type(tool_type).function
    try:
        result = function(ctx, **arguments)
    except Exception as exc:
        message = to_mcp_error(exc)
        if message is None:
            logger.exception("Agent tool {} failed", function.__name__)
            message = INTERNAL_ERROR_MESSAGE
        return {"error": message}
    if isinstance(result, dict) and "error" in result:
        return result
    try:
        facts = tool_type.get_step_facts(ctx, arguments, result)
        if not isinstance(facts, dict):
            raise TypeError("Step facts must be a dictionary")
        facts = json.loads(json.dumps(facts, allow_nan=False))
    except Exception:
        logger.exception("Agent tool {} step facts failed", tool_type.type)
        facts = {}
    return ToolReturn(return_value=result, metadata=facts)


async def _run_tool(
    tool_type: "AgentToolType", ctx: ToolContext, arguments: dict[str, Any]
) -> Any:
    """
    Run a shared tool without blocking the reply's event loop. A stop waits for the
    running tool, so a reply never ends while its tool still changes data.

    :param tool_type: The shared tool and its presentation.
    :param ctx: Who the tool acts for.
    :param arguments: The validated arguments.
    :return: What the tool returned, or an ``error`` message.
    """

    # On the worker's own thread, so tools share its connection and never leak one.
    running = asyncio.ensure_future(
        sync_to_async(_call_tool)(tool_type, ctx, arguments)
    )
    try:
        return await asyncio.shield(running)
    except asyncio.CancelledError:
        await asyncio.wait({running})
        raise


class AgentToolType(Instance):
    """
    A tool an Agent can call: a function shared with the other clients, see
    ``baserow.core.tools``, offered under the name MCP uses for it.

    Agents allow tools by name, so a name is never reused, renaming or removing a
    tool comes with a migration of the allowed tools, and a tool that starts
    changing data gets a new name instead of being allowed where only reads were.
    """

    function: Callable[..., Any]

    group: str
    """The part of the workspace the tool works on, to group tools in the UI."""

    changes_data: bool = False
    """True when the tool creates, changes or deletes data. It then runs alone, and
    new Agents start without it."""

    @property
    def presentation_type(self) -> str:
        """The stable frontend presentation key, independent of execution identity."""

        return self.type

    def get_step_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Summarize a call without exposing its raw arguments.

        :param arguments: The tool's arguments.
        :return: Safe display values, none by default.
        """

        return {}

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        """
        Describe a successful call without exposing its complete result.

        :param ctx: Who acted and where, after the tool checked permissions.
        :param arguments: The validated arguments.
        :param result: The successful tool result.
        :return: Confirmed display values, none by default.
        """

        return {}

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
            return await _run_tool(self, ctx, arguments)

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
