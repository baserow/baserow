import json
from collections import defaultdict, deque
from collections.abc import Callable
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

from .constants import ChatRunEventKind, ChatRunStepStatus
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


def _ended(
    part: ToolReturnPart | RetryPromptPart,
) -> tuple[ChatRunStepStatus, dict[str, Any], ToolErrorCode | None]:
    """Read a tool outcome without confusing domain errors with success.

    :param part: The tool result or validation retry.
    :return: Its status, successful outcome facts and safe failure category.
    """

    if isinstance(part, RetryPromptPart):
        return ChatRunStepStatus.FAILED, {}, ToolErrorCode.INVALID_INPUT
    if part.outcome == "interrupted":
        return ChatRunStepStatus.STOPPED, {}, None
    if part.outcome == "denied":
        return ChatRunStepStatus.FAILED, {}, ToolErrorCode.PERMISSION_DENIED
    if part.outcome != "success" or (
        isinstance(part.content, dict) and "error" in part.content
    ):
        code = (
            part.metadata.get("error_code") if isinstance(part.metadata, dict) else None
        )
        if not isinstance(code, str) or code not in ToolErrorCode:
            code = ToolErrorCode.FAILED
        return ChatRunStepStatus.FAILED, {}, ToolErrorCode(code)
    return ChatRunStepStatus.DONE, _display_data(part.metadata), None


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

    def on_event(self, event: AgentStreamEvent | AgentRunResultEvent) -> None:
        """Start and complete steps, ignoring unrelated model events.

        :param event: One event from the model run.
        """

        if isinstance(event, FunctionToolCallEvent):
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
            presentation_type = description.get("presentation_type")
            step: ChatRunStep = {
                "id": str(uuid4()),
                "tool": name,
                "presentation_type": presentation_type
                if isinstance(presentation_type, str) and presentation_type
                else name,
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
            self._update(step)
        elif isinstance(event, FunctionToolResultEvent):
            pending = self._pending.get(event.tool_call_id)
            if pending:
                step = self._steps[pending.popleft()]
                if not pending:
                    del self._pending[event.tool_call_id]
                status, facts, error_code = _ended(event.part)
                updated = {**step, "status": status, "facts": facts}
                updated.pop("error_code", None)
                if error_code is not None:
                    updated["error_code"] = error_code
                self._update(updated)

    def finish(self) -> list[ChatRunStep]:
        """Finish activity once the model run ends.

        :return: Steps in call order, with unresolved calls marked stopped.
        """

        return stop_running_steps(list(self._steps.values()))

    def _update(self, step: ChatRunStep) -> None:
        self._steps[step["id"]] = step
        self._journal.emit(ChatRunEventKind.STEP, step)
