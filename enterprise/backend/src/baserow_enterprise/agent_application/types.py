from typing import TypedDict


class AgentDefinitionDict(TypedDict):
    id: int
    name: str
    description: str
    instructions: str
    memory: str
    ai_generative_ai_type: str | None
    ai_generative_ai_model: str | None
    ai_temperature: float | None


class AgentTriggerDict(TypedDict):
    id: int
    service: dict
    enabled: bool


class AgentToolDict(TypedDict):
    id: int
    type: str
    name: str
    config: dict
    service: dict | None
    order: int


class AgentChatChannelDict(TypedDict):
    id: int
    type: str
    name: str
    config: dict
    enabled: bool


class AgentApplicationDict(TypedDict):
    id: int
    name: str
    order: int
    type: str
    description: str
    agent_identity_id: int | None
    integrations: list[dict]
    agents: list[AgentDefinitionDict]
    triggers: list[AgentTriggerDict]
    tools: list[AgentToolDict]
    chat_channels: list[AgentChatChannelDict]
