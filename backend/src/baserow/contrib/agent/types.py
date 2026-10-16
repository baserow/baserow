from dataclasses import dataclass
from typing import Literal, TypedDict

from .models import AgentApplication, AgentConversation, AgentMessage

AgentReadinessState = Literal["ready", "incomplete", "unavailable"]


class AgentReadiness(TypedDict):
    state: AgentReadinessState


class AgentConfiguration(AgentReadiness):
    name: str
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
