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
        from baserow.core.trash.registries import trash_item_type_registry

        from .actions import (
            CreateAgentConversationActionType,
            CreateAgentMessageActionType,
            DecideAgentToolApprovalsActionType,
            DeleteAgentConversationActionType,
            UpdateAgentConfigurationActionType,
            UpdateAgentConversationActionType,
        )
        from .application_types import AgentApplicationType
        from .chat_run_type import AgentChatRunType
        from .last_viewed_types import AgentLastViewedItemType
        from .operations import (
            CreateAgentConversationOperationType,
            CreateAgentMessageOperationType,
            DeleteAgentConversationOperationType,
            ReadAgentConfigurationOperationType,
            ReadAgentConversationsOperationType,
            RestoreAgentConversationOperationType,
            UpdateAgentConversationOperationType,
        )
        from .registries import (
            agent_data_provider_type_registry,
            agent_tool_type_registry,
        )
        from .search_types import AgentSearchType
        from .tool_types import (
            CreateDatabaseAgentToolType,
            CreateFieldsAgentToolType,
            CreateRowsAgentToolType,
            CreateTablesAgentToolType,
            CreateViewFiltersAgentToolType,
            CreateViewsAgentToolType,
            DeleteFieldsAgentToolType,
            DeleteRowsAgentToolType,
            GetTableSchemaAgentToolType,
            ListDatabasesAgentToolType,
            ListTableRowsAgentToolType,
            ListTablesAgentToolType,
            ListViewsAgentToolType,
            UpdateDatabaseAgentToolType,
            UpdateFieldsAgentToolType,
            UpdateRowsAgentToolType,
        )
        from .trash_types import AgentConversationTrashableItemType
        from .triggers.actions import (
            CreateAgentTriggerActionType,
            DeleteAgentTriggerActionType,
            UpdateAgentTriggerActionType,
        )
        from .triggers.data_providers import TriggerDataProviderType
        from .triggers.trash_types import AgentTriggerTrashableItemType

        application_type_registry.register(AgentApplicationType())
        workspace_search_registry.register(AgentSearchType())
        last_viewed_item_type_registry.register(AgentLastViewedItemType())
        for operation in (
            ReadAgentConversationsOperationType,
            CreateAgentConversationOperationType,
            CreateAgentMessageOperationType,
            ReadAgentConfigurationOperationType,
            UpdateAgentConversationOperationType,
            DeleteAgentConversationOperationType,
            RestoreAgentConversationOperationType,
        ):
            operation_type_registry.register(operation())
        for action in (
            CreateAgentConversationActionType,
            CreateAgentMessageActionType,
            DecideAgentToolApprovalsActionType,
            UpdateAgentConversationActionType,
            DeleteAgentConversationActionType,
            UpdateAgentConfigurationActionType,
            CreateAgentTriggerActionType,
            UpdateAgentTriggerActionType,
            DeleteAgentTriggerActionType,
        ):
            action_type_registry.register(action())
        trash_item_type_registry.register(AgentConversationTrashableItemType())
        trash_item_type_registry.register(AgentTriggerTrashableItemType())
        chat_run_type_registry.register(AgentChatRunType())
        agent_data_provider_type_registry.register(TriggerDataProviderType())
        for tool_type in (
            ListDatabasesAgentToolType,
            ListTablesAgentToolType,
            GetTableSchemaAgentToolType,
            ListTableRowsAgentToolType,
            ListViewsAgentToolType,
            CreateDatabaseAgentToolType,
            UpdateDatabaseAgentToolType,
            CreateTablesAgentToolType,
            CreateFieldsAgentToolType,
            UpdateFieldsAgentToolType,
            DeleteFieldsAgentToolType,
            CreateViewsAgentToolType,
            CreateViewFiltersAgentToolType,
            CreateRowsAgentToolType,
            UpdateRowsAgentToolType,
            DeleteRowsAgentToolType,
        ):
            agent_tool_type_registry.register(tool_type())

        import baserow.contrib.agent.receivers  # noqa: F401
        import baserow.contrib.agent.triggers.receivers  # noqa: F401
        import baserow.contrib.agent.ws.signals  # noqa: F401
