from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict

from baserow.core.tools.errors import ToolErrorCode

from .constants import ChatRunStepStatus
from .models import ChatRunStatus


class ChatRunStep(TypedDict):
    """A tool call's display summary, shared by live and saved messages."""

    id: str
    tool: str
    status: ChatRunStepStatus
    error_code: NotRequired[ToolErrorCode]
    error_message: NotRequired[str]
    item_errors: NotRequired[list[dict[str, Any]]]
    changes_data: bool
    input: dict[str, Any]
    facts: dict[str, Any]


@dataclass(frozen=True)
class ChatRunOutcome:
    """How a run ended, as its run type reports it."""

    status: ChatRunStatus
    error_code: str = ""
    result: Any = None
