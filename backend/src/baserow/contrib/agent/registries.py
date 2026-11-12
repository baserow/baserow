import asyncio
import inspect
import json
from dataclasses import replace
from typing import Any, Callable, get_type_hints

from asgiref.sync import async_to_sync, sync_to_async
from loguru import logger
from pydantic_ai import RunContext, Tool, ToolReturn
from pydantic_ai.exceptions import ApprovalRequired

from baserow.core.cache import local_cache
from baserow.core.chat_runs.steps import ToolCallInputEvent
from baserow.core.db import with_usable_db_connection
from baserow.core.exceptions import PermissionDenied
from baserow.core.registries import subject_type_registry
from baserow.core.registry import Instance, Registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import classify_tool_error

from .previews import StepPreview, as_requested


def act_as_identity(ctx: ToolContext) -> ToolContext:
    """
    Refresh the Agent identity's authority for one call, so role changes and trash
    apply at once, and record that the identity acted. Which identity and tools a
    reply uses stays fixed for its generation.

    :param ctx: The context the reply started with.
    :return: The context, acting as the refreshed identity.
    :raises PermissionDenied: When the identity is gone or left the workspace.
    """

    subject_type = subject_type_registry.get_by_model(ctx.user)
    subject = subject_type_registry.get_subject(subject_type.type, ctx.user.pk)
    if subject is None or not subject_type.is_in_workspace(subject, ctx.workspace):
        raise PermissionDenied()
    subject_type.track_usage(subject)
    return replace(ctx, user=subject)


def failed_call(tool_type: "AgentToolType", exc: Exception) -> ToolReturn:
    """
    Answer an exception with an error the model can explain.

    :param tool_type: The tool that failed.
    :param exc: What it raised.
    :return: The ``error``, with its code as metadata.
    """

    error = classify_tool_error(exc)
    if error.message is None:
        logger.error("Agent tool {} failed ({})", tool_type.type, type(exc).__name__)
    return ToolReturn(
        return_value={"error": error.to_dict()},
        metadata={"error_code": error.code},
    )


def _step_facts(
    tool_type: "AgentToolType", ctx: ToolContext, arguments: dict[str, Any], result: Any
) -> dict[str, Any]:
    """
    Describe a successful call without letting a broken description fail it.

    :param tool_type: The tool that ran.
    :param ctx: Who acted and where.
    :param arguments: The validated arguments.
    :param result: The tool's result.
    :return: The facts as JSON, or nothing when they can't be built.
    """

    try:
        facts = tool_type.get_step_facts(ctx, arguments, result)
        if not isinstance(facts, dict):
            raise TypeError("Step facts must be a dictionary")
        # The facts stay in the model messages, which must serialize as JSON.
        return json.loads(json.dumps(facts, allow_nan=False))
    except Exception as exc:
        logger.error(
            "Agent tool {} step facts failed ({})", tool_type.type, type(exc).__name__
        )
        return {}


@with_usable_db_connection
def _call_tool(
    tool_type: "AgentToolType",
    ctx: ToolContext,
    arguments: dict[str, Any],
    show_input: Callable[[dict[str, Any]], None],
) -> ToolReturn:
    """
    Show the call's readable request, run the shared tool, and answer an error
    the model can explain instead of failing the reply.

    :param tool_type: The shared tool and how its calls are described.
    :param ctx: Who the tool acts for.
    :param arguments: The validated arguments.
    :param show_input: Adds the readable request to the call's step.
    :return: The result with ``facts`` as metadata, the ``error`` the tool
        returned, or an ``error`` for an exception with ``error_code``.
    """

    function = type(tool_type).function
    try:
        with local_cache.context():
            ctx = act_as_identity(ctx)
            if preview := tool_type.get_step_preview_input(ctx, arguments):
                show_input(preview)
            result = function(ctx, **arguments)
            if isinstance(result, dict) and "error" in result:
                return ToolReturn(return_value=result)
            return ToolReturn(
                return_value=result,
                metadata={"facts": _step_facts(tool_type, ctx, arguments, result)},
            )
    except Exception as exc:
        return failed_call(tool_type, exc)


def input_shower(run_ctx: RunContext) -> Callable[[dict[str, Any]], None]:
    """
    :param run_ctx: The model run of a call.
    :return: A function for the tool's thread that adds the call's readable
        request to its step.
    """

    def show_input(step_input: dict[str, Any]) -> None:
        async_to_sync(run_ctx.emit)(ToolCallInputEvent(input=step_input))

    return show_input


@with_usable_db_connection
def hold_call(
    tool_type: "AgentToolType",
    ctx: ToolContext,
    arguments: dict[str, Any],
    show_input: Callable[[dict[str, Any]], None],
) -> ToolReturn:
    """
    Hold a call for the owner's approval with its request named as the Agent
    identity, so the owner decides on names, not IDs.

    :param tool_type: The held tool.
    :param ctx: Who the call acts for.
    :param arguments: The validated arguments.
    :param show_input: Adds the readable request to the call's step.
    :return: The failure when the identity can no longer act: the call then never
        waits nor runs.
    :raises ApprovalRequired: Otherwise.
    """

    try:
        with local_cache.context():
            ctx = act_as_identity(ctx)
            if preview := tool_type.get_step_preview_input(ctx, arguments):
                show_input(preview)
    except Exception as exc:
        return failed_call(tool_type, exc)
    raise ApprovalRequired()


async def _run_tool(
    tool_type: "AgentToolType",
    ctx: ToolContext,
    arguments: dict[str, Any],
    run_ctx: RunContext,
) -> ToolReturn:
    """
    Run a shared tool without blocking the reply's event loop. A stop waits for the
    running tool, so a reply never ends while its tool still changes data.

    :param tool_type: The shared tool and how its calls are described.
    :param ctx: Who the tool acts for.
    :param arguments: The validated arguments.
    :param run_ctx: The model run, which streams the call's readable request to
        its step.
    :return: What ``_call_tool`` returns.
    """

    # On the worker's own thread, so tools share its connection and never leak one.
    running = asyncio.ensure_future(
        sync_to_async(_call_tool)(tool_type, ctx, arguments, input_shower(run_ctx))
    )
    try:
        return await asyncio.shield(running)
    except asyncio.CancelledError:
        await asyncio.wait({running})
        raise


class AgentToolType(Instance):
    """
    A tool an Agent can call: a function shared with the other clients, see
    ``baserow.core.tools``, offered under a stable name describing its capability.

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

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview | None:
        """
        Describe the request with names instead of IDs, as the Agent identity,
        before the call runs. Whatever can't be named keeps its ID: the tool, not
        the preview, decides whether the call succeeds.

        :param ctx: Who the call acts for, already refreshed.
        :param arguments: The arguments as the model sent them, as JSON values.
        :return: The readable request, or None for a tool without one.
        """

        return None

    def get_step_preview_input(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        The readable request as the step's input stores it, without letting a
        broken preview fail the call.

        :param ctx: Who the call acts for, already refreshed.
        :param arguments: The validated arguments.
        :return: ``values`` and, when part of the request was left out,
            ``truncated``; nothing for a tool without a preview, or when it can't
            be built.
        """

        try:
            preview = self.get_step_preview(ctx, as_requested(arguments))
            return {} if preview is None else preview.to_input()
        except Exception as exc:
            if classify_tool_error(exc).message is None:
                logger.error(
                    "Agent tool {} preview failed ({})", self.type, type(exc).__name__
                )
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

        async def call(run_ctx: RunContext, **arguments: Any) -> Any:
            return await _run_tool(self, ctx, arguments, run_ctx)

        run_parameter = inspect.Parameter(
            "run_ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=RunContext
        )
        call.__signature__ = inspect.Signature([run_parameter, *parameters])
        call.__annotations__ = {
            "run_ctx": RunContext,
            **{parameter.name: hints[parameter.name] for parameter in parameters},
        }
        return Tool(
            call,
            takes_ctx=True,
            name=self.type,
            description=function.__doc__,
            sequential=self.changes_data,
        )


class AgentToolTypeRegistry(Registry[AgentToolType]):
    name = "agent_tool"


agent_tool_type_registry = AgentToolTypeRegistry()
