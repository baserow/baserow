import asyncio
import inspect
import json
from dataclasses import replace
from typing import Any, Callable, get_type_hints

from asgiref.sync import sync_to_async
from loguru import logger
from pydantic_ai import Tool, ToolReturn

from baserow.core.cache import local_cache
from baserow.core.db import with_usable_db_connection
from baserow.core.exceptions import PermissionDenied
from baserow.core.registries import subject_type_registry
from baserow.core.registry import Instance, Registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import INTERNAL_ERROR_MESSAGE, classify_tool_error

StepResources = dict[tuple[str, int], str]


@with_usable_db_connection
def _call_tool(
    tool_type: "AgentToolType", ctx: ToolContext, arguments: dict[str, Any]
) -> ToolReturn | dict[str, Any]:
    """
    Run a shared tool, answering an error the model can explain instead of failing
    the reply.

    :param tool_type: The shared tool and how its calls are described.
    :param ctx: Who the tool acts for.
    :param arguments: The validated arguments.
    :return: The result with the call's facts as metadata, the ``error`` the tool
        returned, or an ``error`` for an exception with its code as metadata.
    """

    function = type(tool_type).function
    try:
        # Identity and tool selection belong to the generation: settings edits
        # apply to the next one, and Stop ends the current one. Refresh only the
        # selected identity's authority, so role changes and trash still apply.
        with local_cache.context():
            subject_type = subject_type_registry.get_by_model(ctx.user)
            subject = subject_type_registry.get_subject(subject_type.type, ctx.user.pk)
            if subject is None or not subject_type.is_in_workspace(
                subject, ctx.workspace
            ):
                raise PermissionDenied()
            subject_type.track_usage(subject)
            ctx = replace(ctx, user=subject)
            result = function(ctx, **arguments)
            if isinstance(result, dict) and "error" in result:
                return result
            try:
                facts = tool_type.get_step_facts(ctx, arguments, result)
                if not isinstance(facts, dict):
                    raise TypeError("Step facts must be a dictionary")
                # The facts stay in the model messages, which must serialize as JSON.
                facts = json.loads(json.dumps(facts, allow_nan=False))
            except Exception as exc:
                logger.error(
                    "Agent tool {} step facts failed ({})",
                    tool_type.type,
                    type(exc).__name__,
                )
                facts = {}
            return ToolReturn(return_value=result, metadata=facts)
    except Exception as exc:
        error = classify_tool_error(exc)
        if error.message is None:
            logger.error(
                "Agent tool {} failed ({})", tool_type.type, type(exc).__name__
            )
        return ToolReturn(
            return_value={"error": error.message or INTERNAL_ERROR_MESSAGE},
            metadata={"error_code": error.code},
        )


async def _run_tool(
    tool_type: "AgentToolType", ctx: ToolContext, arguments: dict[str, Any]
) -> ToolReturn | dict[str, Any]:
    """
    Run a shared tool without blocking the reply's event loop. A stop waits for the
    running tool, so a reply never ends while its tool still changes data.

    :param tool_type: The shared tool and how its calls are described.
    :param ctx: Who the tool acts for.
    :param arguments: The validated arguments.
    :return: What ``_call_tool`` returns.
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

    def get_step_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Select input values that can be displayed to the conversation owner.

        :param arguments: The tool's arguments.
        :return: Approved display values, none by default. Tools must explicitly
            select arguments; never include credentials or execution context.
        """

        return {}

    def get_step_resources(self, result: Any) -> StepResources:
        """
        Extract names already disclosed by this tool's successful result.

        :param result: An authorized successful result, never a failure payload.
        :return: Names keyed by resource namespace and ID. Do not query for names
            or infer them from prose; these describe later calls, not authority.
        """

        return {}

    def get_step_target(
        self, arguments: dict[str, Any], resources: StepResources
    ) -> str | None:
        """Describe a call's target using names already disclosed in this reply.

        :param arguments: The requested tool arguments.
        :param resources: A bounded catalog of previously returned resource names.
        :return: A display name, or None when the target is not known.
        """

        return None

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
