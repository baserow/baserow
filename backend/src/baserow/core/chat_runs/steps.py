import json
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from loguru import logger
from pydantic_ai import AgentRunResultEvent, AgentStreamEvent
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
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


def _ended(part: ToolReturnPart | RetryPromptPart) -> _Ending:
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
            to None for a call the run never offered, which then has no step.
        """

        self._journal = journal
        self._describe_call = describe_call
        self._steps: dict[str, ChatRunStep] = {}
        self._pending: dict[str, deque[str]] = defaultdict(deque)
        self._retrying: dict[str, deque[str]] = defaultdict(deque)
        self._retryable: dict[str, deque[str]] = defaultdict(deque)
        self._failures: dict[str, _Ending] = {}
        self._batch_ended = False

    def on_event(self, event: AgentStreamEvent | AgentRunResultEvent) -> None:
        """Start and complete steps, ignoring unrelated model events.

        :param event: One event from the model run.
        """

        if isinstance(event, FunctionToolCallEvent):
            if self._batch_ended:
                self._retryable, self._retrying = self._retrying, defaultdict(deque)
                self._batch_ended = False
            name = event.part.tool_name
            invalid = event.args_valid is False
            description = {}
            try:
                arguments = {} if invalid else event.part.args_as_dict()
                description = self._describe_call(name, arguments)
            except Exception as exc:
                logger.error("Could not describe tool call ({})", type(exc).__name__)
            if description is None:
                return
            retried = self._retryable[name]
            step: ChatRunStep = {
                "id": retried.popleft() if retried else str(uuid4()),
                "tool": name,
                "status": ChatRunStepStatus.FAILED
                if invalid
                else ChatRunStepStatus.RUNNING,
                "changes_data": description.get("changes_data") is True,
                "input": _display_data(description.get("input")) if not invalid else {},
                "facts": {},
            }
            if invalid:
                step["error_code"] = ToolErrorCode.INVALID_INPUT
            self._pending[event.tool_call_id].append(step["id"])
            self._steps.pop(step["id"], None)
            self._update(step)
        elif isinstance(event, FunctionToolResultEvent):
            self._batch_ended = True
            pending = self._pending.get(event.tool_call_id)
            if pending:
                step = self._steps[pending.popleft()]
                if not pending:
                    del self._pending[event.tool_call_id]
                ending = _ended(event.part)
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
                # The run refused the call itself, so other arguments can't fix it.
                denied = getattr(event.part, "outcome", None) == "denied"
                if updated["status"] == ChatRunStepStatus.FAILED and not denied:
                    self._retrying[updated["tool"]].append(updated["id"])

    def finish(self) -> list[ChatRunStep]:
        """Finish activity once the model run ends.

        :return: Steps in call order, with unresolved calls marked stopped.
        """

        return stop_running_steps(list(self._steps.values()))

    def _update(self, step: ChatRunStep) -> None:
        self._steps[step["id"]] = step
        self._journal.emit(ChatRunEventKind.STEP, step)
