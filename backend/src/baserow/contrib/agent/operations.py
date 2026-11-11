from baserow.core.operations import ApplicationOperationType


class ReadAgentConversationsOperationType(ApplicationOperationType):
    type = "agent_application.read_conversations"


class CreateAgentConversationOperationType(ApplicationOperationType):
    type = "agent_application.create_conversation"


class CreateAgentMessageOperationType(ApplicationOperationType):
    type = "agent_application.create_message"


class ReadAgentConfigurationOperationType(ApplicationOperationType):
    type = "agent_application.read_configuration"


class UpdateAgentConversationOperationType(ApplicationOperationType):
    type = "agent_application.update_conversation"


class DeleteAgentConversationOperationType(ApplicationOperationType):
    type = "agent_application.delete_conversation"


class RestoreAgentConversationOperationType(ApplicationOperationType):
    type = "agent_application.restore_conversation"
