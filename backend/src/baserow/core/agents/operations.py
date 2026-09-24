from baserow.core.operations import WorkspaceCoreOperationType
from baserow.core.registries import OperationType


class ListAgentsWorkspaceOperationType(WorkspaceCoreOperationType):
    type = "workspace.list_agents"
    object_scope_name = "workspace"


class AgentOperationType(OperationType):
    context_scope_name = "workspace"


class CreateAgentOperationType(AgentOperationType):
    type = "agent.create"


class UpdateAgentOperationType(AgentOperationType):
    type = "agent.update"


class DeleteAgentOperationType(AgentOperationType):
    type = "agent.delete"
