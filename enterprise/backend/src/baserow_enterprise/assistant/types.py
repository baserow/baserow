from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal, Optional, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from baserow_enterprise.assistant.utils.helpers import generate_tool_call_id, uuid4_str

StateType = TypeVar("StateType", bound=BaseModel)
PartialStateType = TypeVar("PartialStateType", bound=BaseModel)


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
    id: str | None = Field(default=None, description="The unique UUID of the message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class AssistantMessageType(StrEnum):
    HUMAN = "human"
    AI_MESSAGE = "ai/message"
    AI_THINKING = "ai/thinking"
    AI_ERROR = "ai/error"
    TOOL_CALL = "tool_call"
    TOOL = "tool"
    CHAT_TITLE = "chat/title"


class HumanMessage(BaseMessage):
    id: str = Field(
        default_factory=uuid4_str,
        description="The unique UUID of the message",
    )
    type: Literal["human"] = AssistantMessageType.HUMAN.value
    content: str
    ui_context: Optional[UIContext] = Field(
        default=None, description="The UI context when the message was sent"
    )


class ToolCall(BaseMessage):
    id: str = Field(
        default_factory=generate_tool_call_id,
        description="The unique UUID of the message",
    )
    type: Literal["tool_call"] = Field(
        default=AssistantMessageType.TOOL_CALL.value,
        description="`type` needed to conform to the OpenAI shape, which is expected by LangChain",
    )
    name: str
    args: dict[str, Any]


class ToolCallMessage(BaseMessage):
    id: str = Field(
        default_factory=uuid4_str,
        description="The unique UUID of the message",
    )
    type: Literal["tool"] = AssistantMessageType.TOOL.value
    content: str
    tool_call_id: str
    artifact: Optional[Any] = None


class AiMessage(BaseMessage):
    id: str = Field(
        default_factory=uuid4_str,
        description="The unique UUID of the message",
    )
    type: Literal["ai/message"] = AssistantMessageType.AI_MESSAGE.value
    content: str = Field(default="", description="The AI message content")
    tool_calls: Optional[list[ToolCall]] = Field(
        default_factory=list,
        description="The list of tool calls made by the AI in this message.",
    )

    sources: Optional[list[str]] = Field(
        default=None,
        description="The list of relevant source URLs referenced in the message.",
    )


class THINKING_MESSAGES(StrEnum):
    THINKING = "thinking"
    ANSWERING = "answering"
    # Tool-specific
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    ANALYZE_KNOWLEDGE = "analyze_knowledge"

    # For dynamic messages that don't have a translation in the frontend
    CUSTOM = "custom"


class AiThinkingMessage(BaseMessage):
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


class AiMessageChunk(BaseModel):
    type: Literal["ai/message"] = "ai/message"
    content: str = Field(description="The content of the AI message chunk")


class ChatTitleMessage(BaseMessage):
    type: Literal["chat/title"] = AssistantMessageType.CHAT_TITLE.value
    content: str = Field(description="The chat title")


class AiErrorMessageCode(StrEnum):
    RECURSION_LIMIT_EXCEEDED = "recursion_limit_exceeded"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class AiErrorMessage(BaseMessage):
    type: Literal["ai/error"] = AssistantMessageType.AI_ERROR.value
    code: AiErrorMessageCode = Field(description="The type of error that occurred")
    content: str = Field(description="Error message content")


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


def add_and_merge_sources(
    left: Optional[list[str]], right: Optional[list[str]]
) -> Optional[list[str]]:
    """
    Adds two sets of sources together, returning an empty set if either is explicitly
    set to None.
    """

    # By default these are empty sets, if explicitly None, we want to reset it
    if left is None or right is None:
        return []

    left_set = set(left)

    return list(left) + [s for s in right if s not in left_set]


class _SharedState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    sources: Annotated[Optional[list[str]], add_and_merge_sources] = Field(
        default_factory=list,
        description="The list of relevant source URLs referenced in the last user message.",
    )


class AssistantState(_SharedState):
    messages: Annotated[
        Sequence[AssistantMessageUnion], add_and_merge_messages
    ] = Field(default=[])


class PartialAssistantState(_SharedState):
    messages: Sequence[AssistantMessageUnion] = Field(default=[])
