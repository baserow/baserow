from dataclasses import dataclass
from typing import Any, TypedDict

from baserow.core.chat_runs.constants import ChatRunErrorCode

ASSISTANT_RUN_TYPE = "assistant"
NAVIGATION_EVENT = "navigation"
CHAT_TITLE_EVENT = "chat.title"
ERROR_MODEL_UNAVAILABLE = "model_unavailable"
ERROR_ACCESS_LOST = "access_lost"
NOTHING_RAN_ERROR_CODES = frozenset(
    {ChatRunErrorCode.NOT_STARTED, ERROR_MODEL_UNAVAILABLE, ERROR_ACCESS_LOST}
)


class AssistantRunContext(TypedDict):
    """The sending request data restored by the worker, stored as JSON."""

    human_message_id: int
    client_session_id: str | None
    action_group_id: str
    ui_context: dict[str, Any]
    origin_tab_id: str
    generate_title: bool


@dataclass(frozen=True)
class AssistantRunResult:
    """What a Kuma run produced, saved by its run type when the run ends."""

    text: str
    message_history: bytes
    sources: tuple[str, ...] = ()
    trace_id: str | None = None
    title: str | None = None
    onboarding_target: dict[str, Any] | None = None
