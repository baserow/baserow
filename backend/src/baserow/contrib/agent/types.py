from dataclasses import dataclass
from typing import Literal, TypedDict

from baserow.core.models import Workspace

from .models import AgentApplication, AgentConversation, AgentMessage

AgentReadinessState = Literal["ready", "incomplete", "unavailable"]


class AgentConfiguration(TypedDict):
    readiness: AgentReadinessState
    instructions: str
    provider_type: str | None
    model_identifier: str | None
    errors: dict[str, str]


@dataclass
class AgentMessageCreated:
    conversation: AgentConversation
    message: AgentMessage
    created: bool


@dataclass
class AgentConfigurationUpdated:
    agent: AgentApplication
    changed_fields: list[str]
    configuration: AgentConfiguration


@dataclass(frozen=True)
class AgentReplyRequest:
    turn_id: int
    workspace: Workspace | None
    instructions: str
    provider_type: str
    model_identifier: str
    prompt: str
    history: list[AgentMessage]
