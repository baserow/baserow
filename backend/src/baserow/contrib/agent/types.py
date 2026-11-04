from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from baserow.core.models import Workspace

from .models import AgentApplication, AgentConversation, AgentMessage

AgentReadinessState = Literal["ready", "incomplete", "unavailable"]


@dataclass(frozen=True)
class AgentConfiguration:
    """The saved Agent configuration and its readiness at the time it was read."""

    readiness: AgentReadinessState
    instructions: str
    provider_type: str | None
    model_identifier: str | None
    run_as_subject_type: str | None
    run_as_subject_id: int | None
    errors: dict[str, str]


@dataclass
class AgentMessageCreated:
    """An accepted message, its reply's run, and the conversation's current run."""

    conversation: AgentConversation
    message: AgentMessage
    reply: AgentMessage | None
    run_id: UUID | None
    conversation_run_id: UUID | None
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
    run_as_unavailable: bool = False
    """An identity is configured but cannot be used for workspace access."""
