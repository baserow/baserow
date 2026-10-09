from dataclasses import dataclass

from baserow_enterprise.agent_builder.models import AgentDefinition


@dataclass
class UpdatedAgent:
    agent: AgentDefinition
    original_values: dict
    new_values: dict
