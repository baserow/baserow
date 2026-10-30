from dataclasses import dataclass
from typing import Any, TypedDict

from .constants import ChatRunStepStatus
from .models import ChatRunStatus


class ChatRunStep(TypedDict):
    """A tool call's display summary, shared by live and saved messages."""

    id: str
    tool: str
    presentation_type: str
    status: ChatRunStepStatus
    changes_data: bool
    input: dict[str, Any]
    facts: dict[str, Any]


@dataclass(frozen=True)
class ChatRunOutcome:
    """How a run ended, as its run type reports it."""

    status: ChatRunStatus
    error_code: str = ""
    result: Any = None
