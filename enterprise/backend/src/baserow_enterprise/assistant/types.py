from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal, Optional, Sequence, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from baserow_enterprise.assistant.utils.helpers import generate_tool_call_id

StateType = TypeVar("StateType", bound=BaseModel)
PartialStateType = TypeVar("PartialStateType", bound=BaseModel)


def uuid4_str() -> str:
    """
    Generate a new UUID4 and return it as a string.
    """

    return str(uuid4())


class WorkspaceUIContext(BaseModel):
    id: int
    name: str


class UIContext(BaseModel):
    workspace: WorkspaceUIContext
    timezone: Optional[str] = Field(
        default="UTC", description="The timezone of the user, e.g. 'Europe/Amsterdam'"
    )


class BaseMessage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: Optional[str] = Field(default_factory=uuid4_str)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    artifact: Optional[Any] = None


class HumanMessage(BaseMessage):
    type: Literal["human"] = "human"
    content: str
    ui_context: Optional[UIContext] = Field(
        default=None, description="The UI context when the message was sent"
    )


class ToolCall(BaseMessage):
    type: Literal["tool_call"] = Field(
        default="tool_call",
        description="`type` needed to conform to the OpenAI shape, which is expected by LangChain",
    )
    id: str = Field(
        default_factory=generate_tool_call_id,
        description="Tool call ID in OpenAI format (e.g., 'call_ABC123...')",
    )
    name: str
    args: dict[str, Any]


class ToolCallMessage(BaseMessage):
    type: Literal["tool"] = "tool"
    content: str
    tool_call_id: str
    artifact: Optional[Any] = None


class AiMessage(BaseMessage):
    type: Literal["ai/message"] = "ai/message"
    tool_calls: Optional[list[ToolCall]] = None
    content: str = Field(description="The AI message content")


class THINKING_MESSAGES(StrEnum):
    THINKING = "thinking"
    SEARCHING_DOCS = "searching_docs"
    ANSWERING = "answering"
    ARCHITECTING = "architecting"
    CUSTOM = "custom"


class AiThinkingMessage(BaseMessage):
    type: Literal["ai/thinking"] = "ai/thinking"
    content: str = Field(
        default="", description="Thinking content. Empty signals end of thinking."
    )


class AiInterruptMessage(BaseMessage):
    type: Literal["ai/interrupt"] = "ai/interrupt"
    content: str = Field(description="The AI interrupt message content")


class NavigateToTableArtifact(BaseModel):
    type: Literal["table"] = "table"
    database_id: int
    table_id: int
    table_name: str
    view_id: Optional[int] = None
    view_name: Optional[str] = None


class AiNavigationMessage(BaseMessage):
    type: Literal["ai/navigation"] = "ai/navigation"
    content: str = Field(default="", description="Navigation content.")
    artifact: NavigateToTableArtifact


class AiMessageChunk(BaseModel):
    pass


class ChatTitleMessage(BaseMessage):
    type: Literal["chat/title"] = "chat/title"
    content: str = Field(description="The chat title")


class AiErrorMessageCode(StrEnum):
    RECURSION_LIMIT_EXCEEDED = "recursion_limit_exceeded"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class AiErrorMessage(BaseMessage):
    type: Literal["ai/error"] = "ai/error"
    content: str = Field(description="Error message content")
    code: AiErrorMessageCode = Field(description="The type of error that occurred")


AIMessageUnion = AiMessage | ToolCall | ToolCallMessage | ChatTitleMessage
AssistantMessageUnion = HumanMessage | AIMessageUnion | AiErrorMessage


def add_and_merge_messages(
    left: Sequence[AssistantMessageUnion], right: Sequence[AssistantMessageUnion]
) -> Sequence[AssistantMessageUnion]:
    """
    Merges two lists of messages, updating existing messages by ID.

    By default, this ensures the state is "append-only", unless the new message has the
    same ID as an existing message. new message has the same ID as an existing message.

    :param left: The base list of messages.
    :param right: The list of messages to merge into the base list.

    :return: A new list of messages with the messages from `right` merged into `left`.
        If a message in `right` has the same ID as a message in `left`, the message from
        `right` will replace the message from `left`.
    """

    # coerce to list
    left = list(left)
    right = list(right)

    # merge
    left_idx_by_id = {m.id: i for i, m in enumerate(left)}
    merged = left.copy()
    for m in right:
        if (existing_idx := left_idx_by_id.get(m.id)) is not None:
            merged[existing_idx] = m
        else:
            merged.append(m)

    return merged


class _Shared(BaseModel):
    database_architect_instructions: str | None = Field(
        default=None,
        description="The user's instructions for the database schema design.",
    )


class AssistantState(_Shared):
    messages: Annotated[
        Sequence[AssistantMessageUnion], add_and_merge_messages
    ] = Field(default=[])


class PartialAssistantState(_Shared):
    messages: Sequence[AssistantMessageUnion] = Field(default=[])
