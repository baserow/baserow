from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Callable, Literal, Optional

from django.utils.translation import gettext as _

import dspy
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )


class WorkspaceUIContext(BaseModel):
    id: int
    name: str


class ApplicationUIContext(BaseModel):
    id: str
    name: str


class TableUIContext(BaseModel):
    id: int
    name: str


class ViewUIContext(BaseModel):
    id: int
    name: str
    type: str


class UserUIContext(BaseModel):
    id: int
    name: str
    email: str

    @classmethod
    def from_user(cls, user) -> "UserUIContext":
        return cls(id=user.id, name=user.first_name, email=user.email)


class PageUIContext(BaseModel):
    id: str
    name: str


class WorkflowUIContext(BaseModel):
    id: str
    name: str


class DashboardUIContext(BaseModel):
    id: str
    name: str


class UIContext(BaseModel):
    workspace: WorkspaceUIContext
    # database builder context
    database: Optional[ApplicationUIContext] = None
    table: Optional[TableUIContext] = None
    view: Optional[ViewUIContext] = None
    # application builder context
    application: Optional[ApplicationUIContext] = None
    page: Optional[PageUIContext] = None
    # automation context
    automation: Optional[ApplicationUIContext] = None
    workflow: Optional[WorkflowUIContext] = None
    # dashboard context
    dashboard: Optional[DashboardUIContext] = None
    # user and time context
    user: UserUIContext
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="The UTC timestamp when the message was sent",
    )
    timezone: str = Field(
        default="UTC", description="The timezone of the user, e.g. 'Europe/Amsterdam'"
    )

    @classmethod
    def from_validate_request(cls, request, ui_context_data) -> "UIContext":
        user_context = UserUIContext.from_user(request.user)
        return cls(user=user_context, **ui_context_data)


class AssistantMessageType(StrEnum):
    HUMAN = "human"
    AI_MESSAGE = "ai/message"
    AI_THINKING = "ai/thinking"
    AI_NAVIGATION = "ai/navigation"
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
    timestamp: datetime | None = Field(default=None)
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


class AiThinkingMessage(BaseModel):
    type: Literal["ai/thinking"] = AssistantMessageType.AI_THINKING.value
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


class TableNavigationType(BaseModel):
    type: Literal["database-table"]
    database_id: int
    table_id: int
    table_name: str

    def to_localized_string(self):
        return _("table %(table_name)s") % {"table_name": self.table_name}


class ViewNavigationType(BaseModel):
    type: Literal["database-view"]
    database_id: int
    table_id: int
    view_id: int
    view_name: str

    def to_localized_string(self):
        return _("view %(view_name)s") % {"view_name": self.view_name}


class WorkspaceNavigationType(BaseModel):
    type: Literal["workspace"]

    def to_localized_string(self):
        return _("home")


AnyNavigationType = Annotated[
    TableNavigationType | WorkspaceNavigationType | ViewNavigationType,
    Field(discriminator="type"),
]


class AiNavigationMessage(BaseModel):
    type: Literal["ai/navigation"] = "ai/navigation"
    location: AnyNavigationType


class ToolsUpgradeResponse(BaseModel):
    observation: str
    new_tools: list[dspy.Tool | Callable[[Any], Any]]


class ToolSignature(dspy.Signature):
    """Signature for manual tool handling."""

    question: str = dspy.InputField()
    tools: list[dspy.Tool] = dspy.InputField()
    outputs: dspy.ToolCalls = dspy.OutputField()
