from typing import Any, Literal

from pydantic import Field

from baserow_enterprise.assistant.types import (  # noqa: F401
    AiCancelledMessage,
    AiErrorMessage,
    AiMessage,
    AiMessageChunk,
    AiReasoningChunk,
    AiStartedMessage,
    AiThinkingMessage,
    BaseModel,
    ChatTitleMessage,
)


class ToolCallMessage(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str = Field(description="The tool call id, used to match the result.")
    tool_name: str
    # Normally a dict; args that exceed the payload size limit are truncated
    # to a string and must still render instead of failing validation.
    args: Any = None


class ToolResultMessage(BaseModel):
    type: Literal["tool"] = "tool"
    id: str = Field(description="The tool call id this result belongs to.")
    tool_name: str = ""
    status: Literal["ok", "error"] = "ok"
    content: Any = None


class AiAnswerChunk(BaseModel):
    """
    The partial final answer while it is being streamed. Unlike reasoning it
    is not persisted; the completed answer lands on the message itself.
    """

    type: Literal["ai/answer_chunk"] = "ai/answer_chunk"
    content: str


class ApprovalRequestMessage(BaseModel):
    """
    Emitted when a run pauses because tool calls await approval. The items
    reference the persisted AgentChatToolApproval rows.
    """

    type: Literal["approval_request"] = "approval_request"
    approvals: list[dict[str, Any]] = Field(default_factory=list)


class ApprovalDecidedMessage(BaseModel):
    type: Literal["approval_decided"] = "approval_decided"
    id: int
    status: str
    reason: str = ""


AgentChatEventUnion = (
    AiStartedMessage
    | AiThinkingMessage
    | AiReasoningChunk
    | AiAnswerChunk
    | AiMessageChunk
    | AiMessage
    | AiErrorMessage
    | AiCancelledMessage
    | ChatTitleMessage
    | ToolCallMessage
    | ToolResultMessage
    | ApprovalRequestMessage
    | ApprovalDecidedMessage
)
