import json
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from loguru import logger
from pydantic_ai import AgentRunResultEvent, AgentStreamEvent
from pydantic_ai.messages import (
    DeferredToolRequestsEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolReturnPart,
)

from baserow.core.tools.errors import ToolErrorCode

from .constants import ChatRunEventKind, ChatRunStepStatus
from .types import ChatRunStep, ChatRunWaitingCall

if TYPE_CHECKING:
    from .journal import ChatRunJournal


def stop_running_steps(
    steps: list[ChatRunStep], keep_waiting: bool = False
) -> list[ChatRunStep]:
    """Mark calls with unknown completion as stopped without implying rollback.

    :param steps: The steps in call order.
    :param keep_waiting: Whether held calls stay waiting because the run paused.
    :return: Steps with none left running, and none left waiting unless kept.
    """

    unfinished = {ChatRunStepStatus.RUNNING}
    if not keep_waiting:
        unfinished.add(ChatRunStepStatus.WAITING)
    return [
        {**step, "status": ChatRunStepStatus.STOPPED}
        if step["status"] in unfinished
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
    part: ToolReturnPart | RetryPromptPart, approved: bool
) -> tuple[ChatRunStepStatus, dict[str, Any], ToolErrorCode | None]:
    """Read a tool outcome without confusing domain errors with success.

    :param part: The tool result or validation retry.
    :param approved: Whether the user approved the call, so a denial is not theirs.
    :return: Its status, successful outcome facts and safe failure category.
    """

    if isinstance(part, RetryPromptPart):
        return ChatRunStepStatus.FAILED, {}, ToolErrorCode.INVALID_INPUT
    if part.outcome == "interrupted":
        return ChatRunStepStatus.STOPPED, {}, None
    if part.outcome == "denied" and approved:
        return ChatRunStepStatus.FAILED, {}, ToolErrorCode.PERMISSION_DENIED
    if part.outcome == "denied":
        return ChatRunStepStatus.REJECTED, {}, None
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
        saved_steps: Iterable[ChatRunStep] = (),
        held_step_ids: Mapping[str, str] = MappingProxyType({}),
        approved_ids: Iterable[str] = (),
    ) -> None:
        """
        :param journal: Receives a complete step whenever its state changes.
        :param describe_call: Maps a tool and arguments to safe presentation data, or
            to None for a call the run never offered, which then has no step.
        :param saved_steps: The saved steps of a paused reply, in call order.
        :param held_step_ids: The step id of each held call, by its tool call id.
        :param approved_ids: The tool call ids the user approved.
        """

        self._journal = journal
        self._describe_call = describe_call
        self._steps: dict[str, ChatRunStep] = {step["id"]: step for step in saved_steps}
        self._held_step_ids: dict[str, str] = dict(held_step_ids)
        self._approved_ids = frozenset(approved_ids)
        self._pending: dict[str, deque[str]] = defaultdict(deque)
        self._retrying: dict[str, deque[str]] = defaultdict(deque)
        self._retryable: dict[str, deque[str]] = defaultdict(deque)
        self._batch_ended = False

    def start(self) -> None:
        """Show a resumed reply's saved steps before any of its new activity."""

        for step in self._steps.values():
            self._journal.emit(ChatRunEventKind.STEP, step)

    def on_event(self, event: AgentStreamEvent | AgentRunResultEvent) -> None:
        """Start, hold and complete steps, ignoring unrelated model events.

        :param event: One event from the model run.
        """

        if isinstance(event, FunctionToolCallEvent):
            if self._batch_ended:
                self._retryable, self._retrying = self._retrying, defaultdict(deque)
                self._batch_ended = False
            step_id = self._held_step_ids.pop(event.tool_call_id, None)
            if step_id is None:
                step = self._new_step(event)
                if step is None:
                    return
                step_id = step["id"]
                self._steps.pop(step_id, None)
                self._update(step)
            # pydantic-ai doesn't validate a resumed call it won't run.
            elif event.args_valid is not None:
                running = {**self._steps[step_id], "status": ChatRunStepStatus.RUNNING}
                self._update(running)
            self._pending[event.tool_call_id].append(step_id)
        elif isinstance(event, FunctionToolResultEvent):
            self._batch_ended = True
            pending = self._pending.get(event.tool_call_id)
            if pending:
                step = self._steps[pending.popleft()]
                if not pending:
                    del self._pending[event.tool_call_id]
                status, facts, error_code = _ended(
                    event.part, event.tool_call_id in self._approved_ids
                )
                updated = {**step, "status": status, "facts": facts}
                updated.pop("error_code", None)
                if error_code is not None:
                    updated["error_code"] = error_code
                self._update(updated)
                if isinstance(event.part, RetryPromptPart):
                    self._retrying[updated["tool"]].append(updated["id"])
        elif isinstance(event, DeferredToolRequestsEvent):
            for part in event.requests.approvals:
                pending = self._pending.get(part.tool_call_id)
                if pending:
                    step = self._steps[pending[-1]]
                    self._update({**step, "status": ChatRunStepStatus.WAITING})

    def waiting_calls(self) -> list[ChatRunWaitingCall]:
        """
        :return: The calls held for approval, in call order.
        """

        call_ids = {
            step_id: call_id
            for call_id, step_ids in self._pending.items()
            for step_id in step_ids
        }
        return [
            ChatRunWaitingCall(call_ids[step["id"]], step["id"], step["tool"])
            for step in self._steps.values()
            if step["status"] == ChatRunStepStatus.WAITING and step["id"] in call_ids
        ]

    def finish(self, paused: bool = False) -> list[ChatRunStep]:
        """Finish activity once the model run ends.

        :param paused: Whether the run ended holding calls for approval.
        :return: Steps in call order, with unresolved calls marked stopped.
        """

        return stop_running_steps(list(self._steps.values()), keep_waiting=paused)

    def _new_step(self, event: FunctionToolCallEvent) -> ChatRunStep | None:
        """Describe a new call, failing it at once when its arguments are invalid.

        :param event: The call event.
        :return: Its step, running unless the arguments are invalid, or None for a
            call the run never offered.
        """

        name = event.part.tool_name
        invalid = event.args_valid is False
        description = {}
        try:
            arguments = {} if invalid else event.part.args_as_dict()
            description = self._describe_call(name, arguments)
        except Exception as exc:
            logger.error("Could not describe tool call ({})", type(exc).__name__)
        if description is None:
            return None
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
        return step

    def _update(self, step: ChatRunStep) -> None:
        self._steps[step["id"]] = step
        self._journal.emit(ChatRunEventKind.STEP, step)
