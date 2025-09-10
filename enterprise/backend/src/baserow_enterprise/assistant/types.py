from enum import StrEnum
from typing import Annotated, Any, Literal, Optional, Sequence, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

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
    id: str
    name: str
    args: dict[str, Any]


class ToolMessage(BaseMessage):
    type: Literal["tool"] = "tool"
    content: str
    tool_call_id: str
    ui_payload: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Payload passed through to the frontend - specifically for calls of "
            "contextual tool. Tool call messages without a ui_payload are not passed "
            "through to the frontend."
        ),
    )


class AiMessage(BaseMessage):
    type: Literal["ai/message"] = "ai/message"
    tool_calls: Optional[list[ToolCall]] = None
    content: str = Field(description="The AI message content")


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


AIMessageUnion = AiMessage | ToolCall | ToolMessage | ChatTitleMessage
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


class AssistantState(BaseModel):
    messages: Annotated[
        Sequence[AssistantMessageUnion], add_and_merge_messages
    ] = Field(default=[])


class PartialAssistantState(BaseModel):
    messages: Sequence[AssistantMessageUnion] = Field(default=[])
