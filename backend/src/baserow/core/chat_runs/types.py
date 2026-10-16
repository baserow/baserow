from dataclasses import dataclass
from typing import Any

from .models import ChatRunStatus


@dataclass(frozen=True)
class ChatRunOutcome:
    """How a run ended, as its run type reports it."""

    status: ChatRunStatus
    error_code: str = ""
    result: Any = None
