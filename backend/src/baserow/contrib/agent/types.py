from dataclasses import dataclass, field
from uuid import UUID

from baserow.core.chat_runs.types import ChatRunStep
from baserow.core.models import Workspace
from baserow.core.types import Subject

from .constants import AgentConfigurationErrorCode, AgentReadinessState, AgentRunAsState
from .models import AgentApplication, AgentConversation, AgentMessage


@dataclass(frozen=True)
class AgentRunAsResolution:
    """A configured identity and its availability in the Agent's workspace."""

    status: AgentRunAsState
    subject_type: str | None
    subject_id: int | None
    subject: Subject | None = None
    name: str | None = None


@dataclass(frozen=True)
class AgentConfiguration:
    """The saved Agent configuration and its readiness at the time it was read."""

    readiness: AgentReadinessState
    instructions: str
    provider_type: str | None
    model_identifier: str | None
    run_as: AgentRunAsResolution
    allowed_tools: list[str]
    errors: dict[str, AgentConfigurationErrorCode]


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
    original_values: dict[str, str | int | list[str] | None]
    new_values: dict[str, str | int | list[str] | None]
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
    acting_subject: Subject | None = None
    """Who the tools act as, or None for no workspace access."""
    allowed_tool_names: list[str] = field(default_factory=list)
    """The tools the reply may call, none without an identity to act as."""
    timezone: str | None = None
    """The timezone of the owner, for the dates the tools read and write."""


@dataclass(frozen=True)
class AgentReplyResult:
    """What a reply produced, complete or partial."""

    text: str
    steps: list[ChatRunStep] | None = None
    """Its tool calls in call order, or None when it made none."""
