from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict

from .constants import ChatRunStepErrorCode, ChatRunStepStatus
from .models import ChatRunStatus


class ChatRunStep(TypedDict):
    """A tool call's display summary, shared by live and saved messages."""

    id: str
    tool: str
    presentation_type: str
    status: ChatRunStepStatus
    error_code: NotRequired[ChatRunStepErrorCode]
    changes_data: bool
    input: dict[str, Any]
    facts: dict[str, Any]


@dataclass(frozen=True)
class ChatRunOutcome:
    """How a run ended, as its run type reports it."""

    status: ChatRunStatus
    error_code: str = ""
    result: Any = None
