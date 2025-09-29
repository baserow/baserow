from datetime import datetime
from enum import StrEnum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class WorkspaceUIContext(BaseModel):
    id: int
    name: str


class UIContext(BaseModel):
    workspace: WorkspaceUIContext
    timezone: Optional[str] = Field(
        default="UTC", description="The timezone of the user, e.g. 'Europe/Amsterdam'"
    )


class AssistantMessageType(StrEnum):
    HUMAN = "human"
    AI_MESSAGE = "ai/message"
    AI_THINKING = "ai/thinking"
    AI_ERROR = "ai/error"
    TOOL_CALL = "tool_call"
    TOOL = "tool"
    CHAT_TITLE = "chat/title"


class HumanMessage(BaseModel):
    id: int | None = Field(
        default=None,
        description="The unique UUID of the message",
    )
    type: Literal["human"] = AssistantMessageType.HUMAN.value
    content: str
    ui_context: Optional[UIContext] = Field(
        default=None, description="The UI context when the message was sent"
    )


class AiMessageChunk(BaseModel):
    type: Literal["ai/message"] = "ai/message"
    content: str = Field(description="The content of the AI message chunk")
    sources: Optional[list[str]] = Field(
        default=None,
        description="The list of relevant source URLs referenced in the message.",
    )


class AiMessage(AiMessageChunk):
    id: int | None = Field(
        default=None,
        description="The unique UUID of the message",
    )
    timestamp: datetime | None = Field(default=None)


class THINKING_MESSAGES(StrEnum):
    THINKING = "thinking"
    ANSWERING = "answering"
    # Tool-specific
    SEARCH_DOCS = "search_docs"
    ANALYZE_RESULTS = "analyze_results"

    # For dynamic messages that don't have a translation in the frontend
    CUSTOM = "custom"


class AiThinkingMessage(BaseModel):
    type: Literal["ai/thinking"] = AssistantMessageType.AI_THINKING.value
    code: str = Field(
        default=THINKING_MESSAGES.CUSTOM,
        description="Thinking content. If empty, signals end of thinking.",
    )
    content: str = Field(
        default="",
        description=(
            "A short description of what the AI is thinking about. It can be used to "
            "provide a dynamic message that don't have a translation in the frontend."
        ),
    )


class ChatTitleMessage(BaseModel):
    type: Literal["chat/title"] = AssistantMessageType.CHAT_TITLE.value
    content: str = Field(description="The chat title")


class AiErrorMessageCode(StrEnum):
    RECURSION_LIMIT_EXCEEDED = "recursion_limit_exceeded"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class AiErrorMessage(BaseModel):
    type: Literal["ai/error"] = AssistantMessageType.AI_ERROR.value
    code: AiErrorMessageCode = Field(description="The type of error that occurred")
    content: str = Field(description="Error message content")


AIMessageUnion = (
    AiMessage | AiErrorMessage | AiThinkingMessage | ChatTitleMessage | AiMessageChunk
)
AssistantMessageUnion = HumanMessage | AIMessageUnion
