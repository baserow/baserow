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
            permission_manager_type_registry,
        )
        from baserow.core.search.registries import workspace_search_registry
        from baserow.core.services.registries import service_type_registry
        from baserow.core.trash.registries import trash_item_type_registry

        from .action_tools.action_types import (
            HTTPRequestAgentActionType,
            LocalBaserowAggregateRowsAgentActionType,
            LocalBaserowCreateRowAgentActionType,
            LocalBaserowDeleteRowAgentActionType,
            LocalBaserowGetRowAgentActionType,
            LocalBaserowListRowsAgentActionType,
            LocalBaserowUpdateRowAgentActionType,
            SlackWriteMessageAgentActionType,
            SMTPEmailAgentActionType,
        )
        from .action_tools.actions import (
            CreateAgentActionActionType,
            DeleteAgentActionActionType,
            UpdateAgentActionActionType,
        )
        from .action_tools.data_providers import (
            ToolInputDataProviderType,
            agent_action_data_provider_type_registry,
        )
        from .action_tools.registries import agent_action_type_registry
        from .action_tools.trash_types import AgentActionTrashableItemType
        from .actions import (
            CreateAgentConversationActionType,
            CreateAgentMessageActionType,
            DecideAgentToolApprovalsActionType,
            DeleteAgentConversationActionType,
            LeaveAgentConversationActionType,
            RequestAgentApprovalActionType,
            ShareAgentConversationActionType,
            UpdateAgentConfigurationActionType,
            UpdateAgentConversationActionType,
        )
        from .application_types import AgentApplicationType
        from .channels.actions import (
            CreateAgentChannelActionType,
            DeleteAgentChannelActionType,
            UpdateAgentChannelActionType,
        )
        from .channels.trash_types import AgentChannelTrashableItemType
        from .chat_run_type import AgentChatRunType
        from .last_viewed_types import AgentLastViewedItemType
        from .operations import (
            ApproveAgentToolCallsOperationType,
            ContinueAgentTriggeredConversationOperationType,
            CreateAgentConversationOperationType,
            CreateAgentMessageOperationType,
            DeleteAgentConversationOperationType,
            ReadAgentConfigurationOperationType,
            ReadAgentConversationsOperationType,
            RestoreAgentConversationOperationType,
            UpdateAgentConversationOperationType,
        )
        from .permission_manager import (
            AgentParticipationPermissionManagerType,
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
        from .triggers.dispatcher import agent_trigger_dispatcher
        from .triggers.registries import agent_trigger_type_registry
        from .triggers.trash_types import AgentTriggerTrashableItemType
        from .triggers.trigger_types import (
            ROWS_TRIGGER_TYPES,
            HTTPAgentTriggerType,
            InboundEmailAgentTriggerType,
            PeriodicAgentTriggerType,
            RowsAgentTriggerType,
        )

        application_type_registry.register(AgentApplicationType())
        workspace_search_registry.register(AgentSearchType())
        last_viewed_item_type_registry.register(AgentLastViewedItemType())
        for operation in (
            ReadAgentConversationsOperationType,
            CreateAgentConversationOperationType,
            CreateAgentMessageOperationType,
            ApproveAgentToolCallsOperationType,
            ContinueAgentTriggeredConversationOperationType,
            ReadAgentConfigurationOperationType,
            UpdateAgentConversationOperationType,
            DeleteAgentConversationOperationType,
            RestoreAgentConversationOperationType,
        ):
            operation_type_registry.register(operation())
        permission_manager_type_registry.register(
            AgentParticipationPermissionManagerType()
        )
        for action in (
            CreateAgentConversationActionType,
            CreateAgentMessageActionType,
            DecideAgentToolApprovalsActionType,
            UpdateAgentConversationActionType,
            ShareAgentConversationActionType,
            RequestAgentApprovalActionType,
            LeaveAgentConversationActionType,
            DeleteAgentConversationActionType,
            UpdateAgentConfigurationActionType,
            CreateAgentTriggerActionType,
            UpdateAgentTriggerActionType,
            DeleteAgentTriggerActionType,
            CreateAgentActionActionType,
            UpdateAgentActionActionType,
            DeleteAgentActionActionType,
            CreateAgentChannelActionType,
            UpdateAgentChannelActionType,
            DeleteAgentChannelActionType,
        ):
            action_type_registry.register(action())
        trash_item_type_registry.register(AgentConversationTrashableItemType())
        trash_item_type_registry.register(AgentTriggerTrashableItemType())
        trash_item_type_registry.register(AgentActionTrashableItemType())
        trash_item_type_registry.register(AgentChannelTrashableItemType())
        agent_action_type_registry.register(SMTPEmailAgentActionType())
        agent_action_type_registry.register(HTTPRequestAgentActionType())
        agent_action_type_registry.register(LocalBaserowCreateRowAgentActionType())
        agent_action_type_registry.register(LocalBaserowUpdateRowAgentActionType())
        agent_action_type_registry.register(LocalBaserowDeleteRowAgentActionType())
        agent_action_type_registry.register(LocalBaserowGetRowAgentActionType())
        agent_action_type_registry.register(LocalBaserowListRowsAgentActionType())
        agent_action_type_registry.register(LocalBaserowAggregateRowsAgentActionType())
        agent_action_type_registry.register(SlackWriteMessageAgentActionType())
        agent_trigger_type_registry.register(PeriodicAgentTriggerType())
        agent_trigger_type_registry.register(HTTPAgentTriggerType())
        agent_trigger_type_registry.register(InboundEmailAgentTriggerType())
        for type_name in ROWS_TRIGGER_TYPES:
            agent_trigger_type_registry.register(RowsAgentTriggerType(type_name))
        agent_action_data_provider_type_registry.register(ToolInputDataProviderType())
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
        service_type_registry.add_trigger_listener(agent_trigger_dispatcher.on_event)

        from baserow.core.registries import permission_manager_type_registry

        from .permission_manager import AllowIfTemplatePermissionManagerType

        prev_manager = permission_manager_type_registry.get(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.unregister(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.register(
            AllowIfTemplatePermissionManagerType(prev_manager)
        )

        import baserow.contrib.agent.action_tools.receivers  # noqa: F401
        import baserow.contrib.agent.receivers  # noqa: F401
        import baserow.contrib.agent.triggers.receivers  # noqa: F401
        import baserow.contrib.agent.ws.signals  # noqa: F401
