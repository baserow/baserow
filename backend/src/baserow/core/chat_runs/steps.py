import json
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from loguru import logger
from pydantic_ai import AgentRunResultEvent, AgentStreamEvent
from pydantic_ai.messages import (
    BaseToolCallPart,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    NativeToolCallPart,
    NativeToolReturnPart,
    PartEndEvent,
    PartStartEvent,
    RetryPromptPart,
    ToolReturnPart,
)

from baserow.core.tools.errors import ToolErrorCode

from .constants import (
    MAX_STEP_ITEM_ERRORS,
    MAX_STEP_MESSAGE_LENGTH,
    ChatRunEventKind,
    ChatRunStepStatus,
)
from .tool_input import shorten_text
from .types import ChatRunStep

if TYPE_CHECKING:
    from .journal import ChatRunJournal


def stop_running_steps(steps: list[ChatRunStep]) -> list[ChatRunStep]:
    """Mark calls with unknown completion as stopped without implying rollback.

    :param steps: The steps in call order.
    :return: Steps with none left running.
    """

    return [
        {**step, "status": ChatRunStepStatus.STOPPED}
        if step["status"] == ChatRunStepStatus.RUNNING
        else step
        for step in steps
    ]


def _display_data(value: Any) -> dict[str, Any]:
    """Copy JSON display data without letting metadata break a reply.

    :param value: A tool's display input or outcome facts.
    :return: A JSON-compatible dictionary, or an empty one.
    """

    if not isinstance(value, dict):
        return {}
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except Exception as exc:
        logger.error(
            "Tool step display data is not JSON serializable ({})", type(exc).__name__
        )
        return {}


@dataclass(frozen=True)
class _Ending:
    """How a tool call ended, as its step shows it."""

    status: ChatRunStepStatus
    facts: dict[str, Any] = field(default_factory=dict)
    error_code: ToolErrorCode | None = None
    error_message: str = ""
    item_errors: list[dict[str, Any]] = field(default_factory=list)


def _error_code(value: Any) -> ToolErrorCode:
    """
    Keep only error codes that are safe to show.

    :param value: The code a tool or its metadata reported.
    :return: The code, or ``failed`` when it is not a known one.
    """

    if isinstance(value, str) and value in ToolErrorCode:
        return ToolErrorCode(value)
    return ToolErrorCode.FAILED


def _message(value: Any) -> str:
    """
    Bound a message written for people.

    :param value: The message a tool reported.
    :return: The message, shortened when long, or empty when it isn't text.
    """

    if not isinstance(value, str):
        return ""
    return shorten_text(value, MAX_STEP_MESSAGE_LENGTH)


def _item_errors(content: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Copy what people may see of the failed items: never the model's hints.

    :param content: The tool result.
    :return: The first failed items that have a message, with their name or ID,
        code and message.
    """

    errors = content.get("errors")
    if not isinstance(errors, list):
        return []
    displayable = [
        error
        for error in errors
        if isinstance(error, dict) and _message(error.get("message")).strip()
    ]
    return [
        {
            "item": error.get("item"),
            "code": _error_code(error.get("code")).value,
            "message": _message(error.get("message")),
        }
        for error in displayable[:MAX_STEP_ITEM_ERRORS]
    ]


def _reports_native_failure(content: Any) -> bool:
    """Tell whether a provider-run tool failed while reporting the call itself as
    successful, as Anthropic does with error results and OpenAI with its status.

    :param content: The result the provider reported.
    :return: Whether it describes a failure.
    """

    if not isinstance(content, dict):
        return False
    result_type = content.get("type")
    return (
        "error_code" in content
        or (isinstance(result_type, str) and result_type.endswith("_error"))
        or content.get("status") == "failed"
    )


def _ended(
    part: ToolReturnPart | NativeToolReturnPart | RetryPromptPart,
) -> _Ending:
    """
    Read a tool outcome without confusing domain errors with success.

    :param part: The tool result or validation retry.
    :return: Its status, facts, and what people may see of its failures.
    """

    if isinstance(part, RetryPromptPart):
        return _Ending(ChatRunStepStatus.FAILED, error_code=ToolErrorCode.INVALID_INPUT)
    if part.outcome == "interrupted":
        return _Ending(ChatRunStepStatus.STOPPED)
    if part.outcome == "denied":
        return _Ending(
            ChatRunStepStatus.FAILED, error_code=ToolErrorCode.PERMISSION_DENIED
        )
    if isinstance(part, NativeToolReturnPart):
        if (
            _reports_native_failure(part.content)
            or part.outcome != "success"
            or (isinstance(part.content, dict) and "error" in part.content)
        ):
            return _Ending(ChatRunStepStatus.FAILED, error_code=ToolErrorCode.FAILED)
        return _Ending(ChatRunStepStatus.DONE, facts=_display_data(part.metadata))
    content = part.content if isinstance(part.content, dict) else {}
    metadata = part.metadata if isinstance(part.metadata, dict) else {}
    error = content.get("error")
    if part.outcome != "success" or error is not None:
        error = error if isinstance(error, dict) else {}
        return _Ending(
            ChatRunStepStatus.FAILED,
            error_code=_error_code(error.get("code") or metadata.get("error_code")),
            error_message=_message(error.get("message")),
            item_errors=_item_errors(content),
        )
    if content.get("changed") is False:
        return _Ending(ChatRunStepStatus.SKIPPED)
    return _Ending(
        ChatRunStepStatus.DONE,
        facts=_display_data(metadata),
        item_errors=_item_errors(content),
    )


class ChatRunSteps:
    """Collect ordered tool activity even when a run has no final model result."""

    def __init__(
        self,
        journal: "ChatRunJournal",
        describe_call: Callable[[str, dict[str, Any]], dict[str, Any] | None],
    ) -> None:
        """
        :param journal: Receives a complete step whenever its state changes.
        :param describe_call: Maps a tool and arguments to safe presentation data, or
            to None for a call the run never offered, which then has no step. Calls
            the provider runs itself, such as web searches, are described the same
            way.
        """

        self._journal = journal
        self._describe_call = describe_call
        self._steps: dict[str, ChatRunStep] = {}
        self._pending: dict[str, deque[str]] = defaultdict(deque)
        self._retrying: dict[str, deque[str]] = defaultdict(deque)
        self._retryable: dict[str, deque[str]] = defaultdict(deque)
        self._failures: dict[str, _Ending] = {}
        self._batch_ended = False
        self._hidden_call_started = False

    def on_event(self, event: AgentStreamEvent | AgentRunResultEvent) -> None:
        """Start and complete steps, ignoring unrelated model events.

        :param event: One event from the model run.
        """

        match event:
            case FunctionToolCallEvent(tool_call_id=tool_call_id, part=part):
                if self._batch_ended:
                    self._retryable, self._retrying = (
                        self._retrying,
                        defaultdict(deque),
                    )
                    self._batch_ended = False
                self._start(
                    tool_call_id,
                    part,
                    invalid=event.args_valid is False,
                    retryable=True,
                )
            case FunctionToolResultEvent(tool_call_id=tool_call_id, part=part):
                self._batch_ended = True
                ended = self._end(tool_call_id, part)
                # The run refused the call itself, so other arguments can't fix it.
                denied = getattr(part, "outcome", None) == "denied"
                if (
                    ended is not None
                    and ended["status"] == ChatRunStepStatus.FAILED
                    and not denied
                ):
                    self._retrying[ended["tool"]].append(ended["id"])
            # The provider runs these itself, so they only appear as parts of its
            # response.
            case PartStartEvent(part=NativeToolCallPart() as part):
                self._start(part.tool_call_id, part)
            case PartStartEvent(part=NativeToolReturnPart() as part):
                self._end(part.tool_call_id, part)
            case PartEndEvent(part=NativeToolCallPart() as part):
                self._describe_native_call(part)

    @property
    def started(self) -> bool:
        """Whether the run has called a tool, which a retry could then repeat."""

        return bool(self._steps) or self._hidden_call_started

    def _describe(
        self, part: BaseToolCallPart, invalid: bool = False
    ) -> dict[str, Any] | None:
        """Describe a call without letting a broken description break the reply.

        :param part: The tool call.
        :param invalid: Whether its arguments failed validation.
        :return: The safe presentation data, or None when the call has no step.
        """

        try:
            arguments = {} if invalid else part.args_as_dict()
            return self._describe_call(part.tool_name, arguments)
        except Exception as exc:
            logger.error("Could not describe tool call ({})", type(exc).__name__)
            return {}

    def _start(
        self,
        tool_call_id: str,
        part: BaseToolCallPart,
        invalid: bool = False,
        retryable: bool = False,
    ) -> None:
        """Add the step of a call the model made, unless it has none.

        :param tool_call_id: The call's id, which its result refers to.
        :param part: The tool call.
        :param invalid: Whether its arguments failed validation.
        :param retryable: Whether the call can continue the step of an earlier
            attempt that was sent back for a retry.
        """

        description = self._describe(part, invalid)
        if description is None:
            # A hidden call still ran, so a retry could repeat it.
            self._hidden_call_started = True
            return
        retried = self._retryable[part.tool_name] if retryable else None
        step: ChatRunStep = {
            "id": retried.popleft() if retried else str(uuid4()),
            "tool": part.tool_name,
            "status": ChatRunStepStatus.FAILED
            if invalid
            else ChatRunStepStatus.RUNNING,
            "changes_data": description.get("changes_data") is True,
            "input": _display_data(description.get("input")) if not invalid else {},
            "facts": {},
        }
        if invalid:
            step["error_code"] = ToolErrorCode.INVALID_INPUT
        self._pending[tool_call_id].append(step["id"])
        self._steps.pop(step["id"], None)
        self._update(step)

    def add_failed(self, tool: str, step_input: dict[str, Any]) -> None:
        """Add a failed step that no call of its own reports, such as a search the
        reply could not offer.

        :param tool: The tool the step is about.
        :param step_input: Its safe display input.
        """

        self._update(
            {
                "id": str(uuid4()),
                "tool": tool,
                "status": ChatRunStepStatus.FAILED,
                "changes_data": False,
                "input": _display_data(step_input),
                "facts": {},
                "error_code": ToolErrorCode.FAILED,
            }
        )

    def _describe_native_call(self, part: NativeToolCallPart) -> None:
        """Add what a search looks for, which only arrives after the step started.

        :param part: The complete call.
        """

        pending = self._pending.get(part.tool_call_id)
        if pending:
            step = self._steps[pending[0]]
            step_input = _display_data((self._describe(part) or {}).get("input"))
            if step_input != step["input"]:
                self._update({**step, "input": step_input})

    def _end(
        self,
        tool_call_id: str,
        part: ToolReturnPart | NativeToolReturnPart | RetryPromptPart,
    ) -> ChatRunStep | None:
        """Complete the oldest open step of a call, when it has one.

        :param tool_call_id: The call's id.
        :param part: How the call ended.
        :return: The completed step, or None when the call has no step.
        """

        pending = self._pending.get(tool_call_id)
        if pending:
            step = self._steps[pending.popleft()]
            if not pending:
                del self._pending[tool_call_id]
            ending = _ended(part)
            if ending.status == ChatRunStepStatus.SKIPPED:
                ending = self._failures.get(step["id"], ending)
            if ending.status == ChatRunStepStatus.FAILED:
                self._failures[step["id"]] = ending
            updated = {**step, "status": ending.status, "facts": ending.facts}
            for key in ("error_code", "error_message", "item_errors"):
                updated.pop(key, None)
            if ending.error_code is not None:
                updated["error_code"] = ending.error_code
            if ending.error_message:
                updated["error_message"] = ending.error_message
            if ending.item_errors:
                updated["item_errors"] = ending.item_errors
            self._update(updated)
            return updated
        return None

    def finish(self) -> list[ChatRunStep]:
        """Finish activity once the model run ends.

        :return: Steps in call order, with unresolved calls marked stopped.
        """

        return stop_running_steps(list(self._steps.values()))

    def _update(self, step: ChatRunStep) -> None:
        self._steps[step["id"]] = step
        self._journal.emit(ChatRunEventKind.STEP, step)
