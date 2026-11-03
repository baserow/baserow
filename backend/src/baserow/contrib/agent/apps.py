from django.apps import AppConfig


class AgentConfig(AppConfig):
    name = "baserow.contrib.agent"

    def ready(self):
        from baserow.core.action.registries import action_type_registry
        from baserow.core.chat_runs.registries import chat_run_type_registry
        from baserow.core.registries import (
            application_type_registry,
            last_viewed_item_type_registry,
            operation_type_registry,
        )
        from baserow.core.search.registries import workspace_search_registry

        from .actions import (
            CreateAgentConversationActionType,
            CreateAgentMessageActionType,
            UpdateAgentConfigurationActionType,
        )
        from .application_types import AgentApplicationType
        from .chat_run_type import AgentChatRunType
        from .last_viewed_types import AgentLastViewedItemType
        from .operations import (
            CreateAgentConversationOperationType,
            CreateAgentMessageOperationType,
            ReadAgentConfigurationOperationType,
            ReadAgentConversationsOperationType,
        )
        from .search_types import AgentSearchType

        application_type_registry.register(AgentApplicationType())
        workspace_search_registry.register(AgentSearchType())
        last_viewed_item_type_registry.register(AgentLastViewedItemType())
        for operation in (
            ReadAgentConversationsOperationType,
            CreateAgentConversationOperationType,
            CreateAgentMessageOperationType,
            ReadAgentConfigurationOperationType,
        ):
            operation_type_registry.register(operation())
        for action in (
            CreateAgentConversationActionType,
            CreateAgentMessageActionType,
            UpdateAgentConfigurationActionType,
        ):
            action_type_registry.register(action())
        chat_run_type_registry.register(AgentChatRunType())

        import baserow.contrib.agent.receivers  # noqa: F401
        import baserow.contrib.agent.ws.signals  # noqa: F401
