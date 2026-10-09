from abc import ABC

from baserow.core.registries import OperationType


class AgentBuilderOperationType(OperationType, ABC):
    context_scope_name = "agent_builder"


class CreateAgentOperationType(AgentBuilderOperationType):
    type = "agent_builder.create_agent"


class ListAgentsOperationType(AgentBuilderOperationType):
    type = "agent_builder.list_agents"
    object_scope_name = "agent_builder_agent"


class OrderAgentsOperationType(AgentBuilderOperationType):
    type = "agent_builder.order_agents"


class AgentOperationType(OperationType, ABC):
    context_scope_name = "agent_builder_agent"


class ReadAgentOperationType(AgentOperationType):
    type = "agent_builder_agent.read"


class UpdateAgentOperationType(AgentOperationType):
    type = "agent_builder_agent.update"


class DeleteAgentOperationType(AgentOperationType):
    type = "agent_builder_agent.delete"


class RestoreAgentOperationType(AgentOperationType):
    type = "agent_builder_agent.restore"
