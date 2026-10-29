from dataclasses import dataclass, field
from typing import Literal, TypedDict
from uuid import UUID

from baserow.core.models import Workspace
from baserow.core.types import Subject

from .models import AgentApplication, AgentConversation, AgentMessage

AgentReadinessState = Literal["ready", "incomplete", "unavailable"]


class AgentConfiguration(TypedDict):
    readiness: AgentReadinessState
    instructions: str
    provider_type: str | None
    model_identifier: str | None
    run_as_subject_type: str | None
    run_as_subject_id: int | None
    allowed_tools: list[str]
    errors: dict[str, str]


@dataclass
class AgentMessageCreated:
    conversation: AgentConversation
    message: AgentMessage
    reply: AgentMessage | None
    run_id: UUID | None
    created: bool


@dataclass
class AgentConfigurationUpdated:
    agent: AgentApplication
    changed_fields: list[str]
    configuration: AgentConfiguration


@dataclass(frozen=True)
class AgentReplyRequest:
    reply_id: int
    workspace: Workspace | None
    instructions: str
    provider_type: str
    model_identifier: str
    prompt: str
    history: list[AgentMessage]
    acting_subject: Subject | None = None
    """Who the tools act as, or None for no workspace access."""
    allowed_tool_names: list[str] = field(default_factory=list)
    """The tools the reply may call, none without an identity to act as."""
    timezone: str | None = None
    """The timezone of the owner, for the dates the tools read and write."""


@dataclass(frozen=True)
class AgentReplyResult:
    text: str
    provider_type: str | None = None
    model_identifier: str | None = None
    model_messages: list[dict] | None = None
    usage: dict | None = None
