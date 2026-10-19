from dataclasses import dataclass, field

ASSISTANT_RUN_TYPE = "assistant"
NAVIGATION_EVENT = "navigation"
CHAT_TITLE_EVENT = "chat.title"
ERROR_MODEL_UNAVAILABLE = "model_unavailable"


@dataclass(frozen=True)
class AssistantRunResult:
    """What a Kuma run produced, saved by its run type when the run ends."""

    text: str
    message_history: bytes
    sources: list[str] = field(default_factory=list)
    trace_id: str | None = None
    title: str | None = None
    onboarding_target: dict | None = None
