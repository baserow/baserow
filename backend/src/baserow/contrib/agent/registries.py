import asyncio
import inspect
import json
from dataclasses import replace
from typing import Any, Callable, get_type_hints

from django.core.exceptions import ValidationError as DjangoValidationError

from asgiref.sync import sync_to_async
from pydantic import ValidationError
from pydantic_ai import Tool, ToolReturn
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.exceptions import RequestBodyValidationException
from baserow.core.cache import local_cache
from baserow.core.db import with_usable_db_connection
from baserow.core.chat_runs.constants import ChatRunStepErrorCode
from baserow.core.exceptions import (
    InstanceTypeDoesNotExist,
    PermissionDenied,
    PermissionException,
    UserNotInWorkspace,
)
from baserow.core.registries import subject_type_registry
from baserow.core.registry import Instance, Registry
from baserow.core.sentry import report_exception
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import (
    INTERNAL_ERROR_MESSAGE,
    ToolInputError,
    _is_does_not_exist,
    tool_error_message,
)

def _tool_error_code(exc: Exception) -> ChatRunStepErrorCode:
    """Classify failures at the same privacy boundary as the model's error text.

    :param exc: The original exception, never inspected for message content.
    :return: A fixed category safe for a translated frontend explanation.
    """

    # Match the shared tools' existence hiding across workspaces.
    if isinstance(exc, UserNotInWorkspace):
        return ChatRunStepErrorCode.NOT_FOUND
    if isinstance(exc, (PermissionException, DRFPermissionDenied)):
        return ChatRunStepErrorCode.PERMISSION_DENIED
    if isinstance(
        exc,
        (
            ToolInputError,
            DjangoValidationError,
            RequestBodyValidationException,
            DRFValidationError,
            ValidationError,
        ),
    ):
        return ChatRunStepErrorCode.INVALID_INPUT
    if isinstance(exc, InstanceTypeDoesNotExist):
        return (
            ChatRunStepErrorCode.INVALID_INPUT
            if exc.args
            else ChatRunStepErrorCode.FAILED
        )
    if _is_does_not_exist(exc):
        return ChatRunStepErrorCode.NOT_FOUND
    return ChatRunStepErrorCode.FAILED


@with_usable_db_connection
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
                facts = json.loads(json.dumps(facts, allow_nan=False))
            except Exception as exc:
                report_exception(
                    exc,
                    f"Agent tool {tool_type.type} step facts failed",
                    context={"tool": tool_type.type, "phase": "step_facts"},
                )
                facts = {}
            return ToolReturn(return_value=result, metadata=facts)
    except Exception as exc:
        message = tool_error_message(exc)
        if message is None:
            report_exception(
                exc,
                f"Agent tool {tool_type.type} failed",
                context={"tool": tool_type.type, "phase": "execution"},
            )
            message = INTERNAL_ERROR_MESSAGE
        return ToolReturn(
            return_value={"error": message},
            metadata={"error_code": _tool_error_code(exc)},
        )


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
        Describe a call before it runs, from its arguments alone.

        :param arguments: The tool's arguments, possibly invalid.
        :return: Display values derived from the arguments, none by default. Never
            copy argument values, which can hold private data.
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
