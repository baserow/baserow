from abc import ABCMeta

from baserow.core.registries import OperationType


class AgentApplicationOperationType(OperationType, metaclass=ABCMeta):
    context_scope_name = "application"


class ReadAgentDefinitionOperationType(AgentApplicationOperationType):
    type = "agent_application.read_agent"


class UpdateAgentDefinitionOperationType(AgentApplicationOperationType):
    type = "agent_application.update_agent"


class ReadAgentTriggerOperationType(AgentApplicationOperationType):
    type = "agent_application.read_trigger"


class UpdateAgentTriggerOperationType(AgentApplicationOperationType):
    type = "agent_application.update_trigger"


class ListAgentToolsOperationType(AgentApplicationOperationType):
    type = "agent_application.list_tools"


class CreateAgentToolOperationType(AgentApplicationOperationType):
    type = "agent_application.create_tool"


class UpdateAgentToolOperationType(AgentApplicationOperationType):
    type = "agent_application.update_tool"


class DeleteAgentToolOperationType(AgentApplicationOperationType):
    type = "agent_application.delete_tool"


class ListAgentChatsOperationType(AgentApplicationOperationType):
    type = "agent_application.list_chats"


class ReadAgentChatOperationType(AgentApplicationOperationType):
    type = "agent_application.read_chat"


class RunAgentChatOperationType(AgentApplicationOperationType):
    type = "agent_application.run_chat"


class CancelAgentChatOperationType(AgentApplicationOperationType):
    type = "agent_application.cancel_chat"


class DeleteAgentChatOperationType(AgentApplicationOperationType):
    type = "agent_application.delete_chat"


class ReadAgentUsageOperationType(AgentApplicationOperationType):
    type = "agent_application.read_usage"


class DecideAgentToolApprovalOperationType(AgentApplicationOperationType):
    type = "agent_application.decide_tool_approval"


class ReadAgentChatChannelOperationType(AgentApplicationOperationType):
    type = "agent_application.read_chat_channel"


class UpdateAgentChatChannelOperationType(AgentApplicationOperationType):
    type = "agent_application.update_chat_channel"
