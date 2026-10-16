from django.apps import AppConfig


class AgentConfig(AppConfig):
    name = "baserow.contrib.agent"

    def ready(self):
        from baserow.contrib.agent.actions import (
            CreateAgentConversationActionType,
            CreateAgentMessageActionType,
            UpdateAgentConfigurationActionType,
        )
        from baserow.contrib.agent.application_types import AgentApplicationType
        from baserow.contrib.agent.operations import (
            CreateAgentConversationOperationType,
            CreateAgentMessageOperationType,
            ReadAgentConversationsOperationType,
            ReadAgentSettingsOperationType,
        )
        from baserow.contrib.agent.search_types import AgentSearchType
        from baserow.core.action.registries import action_type_registry
        from baserow.core.registries import (
            application_type_registry,
            operation_type_registry,
        )
        from baserow.core.search.registries import workspace_search_registry

        application_type_registry.register(AgentApplicationType())
        workspace_search_registry.register(AgentSearchType())
        for operation in (
            ReadAgentConversationsOperationType,
            CreateAgentConversationOperationType,
            CreateAgentMessageOperationType,
            ReadAgentSettingsOperationType,
        ):
            operation_type_registry.register(operation())
        for action in (
            CreateAgentConversationActionType,
            CreateAgentMessageActionType,
            UpdateAgentConfigurationActionType,
        ):
            action_type_registry.register(action())
