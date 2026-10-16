from baserow.core.operations import ApplicationOperationType


class ReadAgentConversationsOperationType(ApplicationOperationType):
    type = "agent_application.read_conversations"


class CreateAgentConversationOperationType(ApplicationOperationType):
    type = "agent_application.create_conversation"


class CreateAgentMessageOperationType(ApplicationOperationType):
    type = "agent_application.create_message"


class ReadAgentSettingsOperationType(ApplicationOperationType):
    type = "agent_application.read_settings"
