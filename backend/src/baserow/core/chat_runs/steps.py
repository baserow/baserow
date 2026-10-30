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
    except Exception:
        logger.exception("Tool step display data is not JSON serializable")
        return {}


def _ended(
    part: ToolReturnPart | RetryPromptPart,
) -> tuple[ChatRunStepStatus, dict[str, Any]]:
    """Read a tool outcome without confusing domain errors with success.

    :param part: The tool result or validation retry.
    :return: Its display status and successful outcome facts.
    """

    if isinstance(part, RetryPromptPart):
        return ChatRunStepStatus.FAILED, {}
    if part.outcome == "interrupted":
        return ChatRunStepStatus.STOPPED, {}
    if part.outcome != "success" or (
        isinstance(part.content, dict)
        and ("error" in part.content or part.content.get("errors"))
    ):
        return ChatRunStepStatus.FAILED, {}
    return ChatRunStepStatus.DONE, _display_data(part.metadata)


class ChatRunSteps:
    """Collect ordered tool activity even when a run has no final model result."""

    def __init__(
        self,
        journal: "ChatRunJournal",
        describe_call: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> None:
        """
        :param journal: Receives a complete step whenever its state changes.
        :param describe_call: Maps a tool and arguments to safe presentation data.
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
                if not isinstance(description, dict):
                    description = {}
            except Exception:
                logger.exception("Could not describe tool call {}", name)
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
            self._pending[event.tool_call_id].append(step["id"])
            self._update(step)
        elif isinstance(event, FunctionToolResultEvent):
            pending = self._pending.get(event.tool_call_id)
            if pending:
                step = self._steps[pending.popleft()]
                if not pending:
                    del self._pending[event.tool_call_id]
                status, facts = _ended(event.part)
                self._update({**step, "status": status, "facts": facts})

    def finish(self) -> list[ChatRunStep]:
        """Finish activity once the model run ends.

        :return: Steps in call order, with unresolved calls marked stopped.
        """

        return stop_running_steps(list(self._steps.values()))

    def _update(self, step: ChatRunStep) -> None:
        self._steps[step["id"]] = step
        self._journal.emit(ChatRunEventKind.STEP, step)
