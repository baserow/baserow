from django.apps import AppConfig


class AutomationConfig(AppConfig):
    name = "baserow.contrib.automation"

    def ready(self):
        from baserow.contrib.automation.action_scopes import WorkflowActionScopeType
        from baserow.contrib.automation.application_types import (
            AutomationApplicationType,
        )
        from baserow.contrib.automation.nodes.actions import (
            CreateAutomationNodeActionType,
            DeleteAutomationNodeActionType,
            DuplicateAutomationNodeActionType,
            MoveAutomationNodeActionType,
            ReplaceAutomationNodeActionType,
            UpdateAutomationNodeActionType,
        )
        from baserow.contrib.automation.nodes.node_types import (
            AIAgentActionNodeType,
            CoreCSVFileReaderActionNodeType,
            CoreGotoActionNodeType,
            CoreHTTPRequestActionNodeType,
            CoreHTTPTriggerNodeType,
            CoreInboundEmailTriggerNodeType,
            CoreIteratorActionNodeType,
            CoreManualTriggerNodeType,
            CorePeriodicTriggerNodeType,
            CoreResponseActionNodeType,
            CoreRouterActionNodeType,
            CoreSMTPEmailActionNodeType,
            CoreStartWorkflowActionNodeType,
            LocalBaserowAggregateRowsActionNodeType,
            LocalBaserowCreateRowActionNodeType,
            LocalBaserowCreateRowsActionNodeType,
            LocalBaserowDeleteRowActionNodeType,
            LocalBaserowFieldsUpdatedTriggerNodeType,
            LocalBaserowGetRowActionNodeType,
            LocalBaserowListRowsActionNodeType,
            LocalBaserowRowsCreatedTriggerNodeType,
            LocalBaserowRowsDeletedTriggerNodeType,
            LocalBaserowRowsUpdatedTriggerNodeType,
            LocalBaserowUpdateRowActionNodeType,
            LocalBaserowUpdateRowsActionNodeType,
            SlackWriteMessageActionNodeType,
        )
        from baserow.contrib.automation.nodes.object_scopes import (
            AutomationNodeObjectScopeType,
        )
        from baserow.contrib.automation.nodes.operations import (
            CreateAutomationNodeOperationType,
            DeleteAutomationNodeOperationType,
            DuplicateAutomationNodeOperationType,
            ListAutomationNodeOperationType,
            OrderAutomationNodeOperationType,
            ReadAutomationNodeOperationType,
            RestoreAutomationNodeOperationType,
            UpdateAutomationNodeOperationType,
        )
        from baserow.contrib.automation.nodes.registries import (
            ReplaceAutomationNodeTrashOperationType,
            automation_node_type_registry,
        )
        from baserow.contrib.automation.nodes.trash_types import (
            AutomationNodeTrashableItemType,
        )
        from baserow.contrib.automation.object_scopes import AutomationObjectScopeType
        from baserow.contrib.automation.operations import (
            ListAutomationWorkflowsOperationType,
            OrderAutomationWorkflowsOperationType,
        )
        from baserow.contrib.automation.trash_types import AutomationTrashableItemType
        from baserow.contrib.automation.workflows.actions import (
            CreateAutomationWorkflowActionType,
            DeleteAutomationWorkflowActionType,
            DuplicateAutomationWorkflowActionType,
            OrderAutomationWorkflowActionType,
            UpdateAutomationWorkflowActionType,
        )
        from baserow.contrib.automation.workflows.job_types import (
            DuplicateAutomationWorkflowJobType,
            PublishAutomationWorkflowJobType,
        )
        from baserow.contrib.automation.workflows.object_scopes import (
            AutomationWorkflowObjectScopeType,
        )
        from baserow.contrib.automation.workflows.operations import (
            CreateAutomationWorkflowOperationType,
            DeleteAutomationWorkflowOperationType,
            DuplicateAutomationWorkflowOperationType,
            PublishAutomationWorkflowOperationType,
            ReadAutomationWorkflowOperationType,
            RestoreAutomationWorkflowOperationType,
            UpdateAutomationWorkflowOperationType,
        )
        from baserow.contrib.automation.workflows.trash_types import (
            AutomationWorkflowTrashableItemType,
        )
        from baserow.core.action.registries import (
            action_scope_registry,
            action_type_registry,
        )
        from baserow.core.jobs.registries import job_type_registry
        from baserow.core.notifications.registries import notification_type_registry
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
        )
        from baserow.core.trash.registries import trash_item_type_registry

        application_type_registry.register(AutomationApplicationType())

        object_scope_type_registry.register(AutomationObjectScopeType())
        object_scope_type_registry.register(AutomationWorkflowObjectScopeType())
        object_scope_type_registry.register(AutomationNodeObjectScopeType())

        from baserow.contrib.automation.workflows.last_viewed_types import (
            AutomationWorkflowLastViewedItemType,
        )
        from baserow.core.registries import last_viewed_item_type_registry

        last_viewed_item_type_registry.register(AutomationWorkflowLastViewedItemType())

        operation_type_registry.register(CreateAutomationWorkflowOperationType())
        operation_type_registry.register(DeleteAutomationWorkflowOperationType())
        operation_type_registry.register(DuplicateAutomationWorkflowOperationType())
        operation_type_registry.register(ReadAutomationWorkflowOperationType())
        operation_type_registry.register(UpdateAutomationWorkflowOperationType())
        operation_type_registry.register(ListAutomationWorkflowsOperationType())
        operation_type_registry.register(OrderAutomationWorkflowsOperationType())
        operation_type_registry.register(RestoreAutomationWorkflowOperationType())
        operation_type_registry.register(PublishAutomationWorkflowOperationType())
        operation_type_registry.register(ListAutomationNodeOperationType())
        operation_type_registry.register(CreateAutomationNodeOperationType())
        operation_type_registry.register(UpdateAutomationNodeOperationType())
        operation_type_registry.register(ReadAutomationNodeOperationType())
        operation_type_registry.register(DeleteAutomationNodeOperationType())
        operation_type_registry.register(RestoreAutomationNodeOperationType())
        operation_type_registry.register(DuplicateAutomationNodeOperationType())
        operation_type_registry.register(OrderAutomationNodeOperationType())

        job_type_registry.register(DuplicateAutomationWorkflowJobType())
        job_type_registry.register(PublishAutomationWorkflowJobType())

        trash_item_type_registry.register(AutomationTrashableItemType())
        trash_item_type_registry.register(AutomationWorkflowTrashableItemType())
        trash_item_type_registry.register(AutomationNodeTrashableItemType())

        action_type_registry.register(CreateAutomationWorkflowActionType())
        action_type_registry.register(UpdateAutomationWorkflowActionType())
        action_type_registry.register(DeleteAutomationWorkflowActionType())
        action_type_registry.register(DuplicateAutomationWorkflowActionType())
        action_type_registry.register(OrderAutomationWorkflowActionType())
        action_type_registry.register(CreateAutomationNodeActionType())
        action_type_registry.register(UpdateAutomationNodeActionType())
        action_type_registry.register(DeleteAutomationNodeActionType())
        action_type_registry.register(DuplicateAutomationNodeActionType())
        action_type_registry.register(ReplaceAutomationNodeActionType())
        action_type_registry.register(MoveAutomationNodeActionType())

        from baserow.contrib.automation.notification_types import (
            WorkflowDisabledNotificationType,
        )

        notification_type_registry.register(WorkflowDisabledNotificationType())

        action_scope_registry.register(WorkflowActionScopeType())

        from baserow.contrib.automation.mcp.nodes.tools import (
            AddNodesMcpTool,
            DeleteNodesMcpTool,
            ListNodesMcpTool,
            UpdateNodesMcpTool,
        )
        from baserow.contrib.automation.mcp.workflows.tools import (
            CreateWorkflowsMcpTool,
            ListWorkflowsMcpTool,
        )
        from baserow.core.mcp.groups import (
            AutomationDeleteMCPToolGroup,
            AutomationEditMCPToolGroup,
            AutomationReadMCPToolGroup,
            mcp_tool_group_registry,
        )
        from baserow.core.mcp.registries import mcp_tool_registry

        mcp_tool_group_registry.register(AutomationReadMCPToolGroup())
        mcp_tool_group_registry.register(AutomationEditMCPToolGroup())
        mcp_tool_group_registry.register(AutomationDeleteMCPToolGroup())
        mcp_tool_registry.register(ListWorkflowsMcpTool())
        mcp_tool_registry.register(ListNodesMcpTool())
        mcp_tool_registry.register(CreateWorkflowsMcpTool())
        mcp_tool_registry.register(AddNodesMcpTool())
        mcp_tool_registry.register(UpdateNodesMcpTool())
        mcp_tool_registry.register(DeleteNodesMcpTool())

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

        automation_node_type_registry.register(LocalBaserowCreateRowActionNodeType())
        automation_node_type_registry.register(LocalBaserowCreateRowsActionNodeType())
        automation_node_type_registry.register(LocalBaserowUpdateRowActionNodeType())
        automation_node_type_registry.register(LocalBaserowUpdateRowsActionNodeType())
        automation_node_type_registry.register(LocalBaserowDeleteRowActionNodeType())
        automation_node_type_registry.register(LocalBaserowGetRowActionNodeType())
        automation_node_type_registry.register(LocalBaserowListRowsActionNodeType())
        automation_node_type_registry.register(
            LocalBaserowAggregateRowsActionNodeType()
        )
        automation_node_type_registry.register(CoreHTTPRequestActionNodeType())
        automation_node_type_registry.register(CoreIteratorActionNodeType())
        automation_node_type_registry.register(CoreCSVFileReaderActionNodeType())
        automation_node_type_registry.register(CoreSMTPEmailActionNodeType())
        automation_node_type_registry.register(CoreRouterActionNodeType())
        automation_node_type_registry.register(CoreStartWorkflowActionNodeType())
        automation_node_type_registry.register(CoreGotoActionNodeType())
        automation_node_type_registry.register(CoreResponseActionNodeType())
        automation_node_type_registry.register(LocalBaserowRowsCreatedTriggerNodeType())
        automation_node_type_registry.register(LocalBaserowRowsUpdatedTriggerNodeType())
        automation_node_type_registry.register(LocalBaserowRowsDeletedTriggerNodeType())
        automation_node_type_registry.register(
            LocalBaserowFieldsUpdatedTriggerNodeType()
        )
        automation_node_type_registry.register(CorePeriodicTriggerNodeType())
        automation_node_type_registry.register(CoreHTTPTriggerNodeType())
        automation_node_type_registry.register(CoreInboundEmailTriggerNodeType())
        automation_node_type_registry.register(CoreManualTriggerNodeType())
        automation_node_type_registry.register(AIAgentActionNodeType())
        automation_node_type_registry.register(SlackWriteMessageActionNodeType())

        from baserow.core.trash.registries import trash_operation_type_registry

        trash_operation_type_registry.register(
            ReplaceAutomationNodeTrashOperationType()
        )

        from baserow.contrib.automation.data_providers.data_provider_types import (
            CurrentIterationDataProviderType,
            CurrentNodeDataProviderType,
            PreviousNodeProviderType,
        )
        from baserow.contrib.automation.data_providers.registries import (
            automation_data_provider_type_registry,
        )

        automation_data_provider_type_registry.register(PreviousNodeProviderType())
        automation_data_provider_type_registry.register(
            CurrentIterationDataProviderType()
        )
        automation_data_provider_type_registry.register(CurrentNodeDataProviderType())

        from baserow.contrib.automation.nodes.permission_manager import (
            AutomationNodePermissionManager,
        )
        from baserow.contrib.automation.workflows.permission_manager import (
            AutomationWorkflowPermissionManager,
        )
        from baserow.core.registries import permission_manager_type_registry

        permission_manager_type_registry.register(AutomationWorkflowPermissionManager())
        permission_manager_type_registry.register(AutomationNodePermissionManager())

        # The signals must always be imported last because they use
        # the registries which need to be filled first.
        import baserow.contrib.automation.nodes.ws.signals  # noqa: F403, F401
        import baserow.contrib.automation.workflows.receivers  # noqa: F401
        import baserow.contrib.automation.workflows.signals  # noqa: F403, F401
        import baserow.contrib.automation.workflows.ws.signals  # noqa: F403, F401
        import baserow.contrib.integrations.tasks  # noqa: F403, F401
        from baserow.contrib.automation.nodes.receivers import (
            connect_to_node_pre_delete_signal,
        )

        connect_to_node_pre_delete_signal()

        from baserow.contrib.automation.search_types import AutomationSearchType
        from baserow.core.search.registries import workspace_search_registry

        workspace_search_registry.register(AutomationSearchType())
