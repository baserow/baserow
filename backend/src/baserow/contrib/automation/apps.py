from django.apps import AppConfig

from baserow.core.feature_flags import FF_AUTOMATION, feature_flag_is_enabled


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
            OrderAutomationNodesActionType,
            ReplaceAutomationNodeActionType,
            UpdateAutomationNodeActionType,
        )
        from baserow.contrib.automation.nodes.node_types import (
            CoreHttpRequestNodeType,
            CoreSMTPEmailNodeType,
            LocalBaserowAggregateRowsNodeType,
            LocalBaserowCreateRowNodeType,
            LocalBaserowDeleteRowNodeType,
            LocalBaserowGetRowNodeType,
            LocalBaserowListRowsNodeType,
            LocalBaserowRowsCreatedNodeTriggerType,
            LocalBaserowRowsDeletedNodeTriggerType,
            LocalBaserowRowsUpdatedNodeTriggerType,
            LocalBaserowUpdateRowNodeType,
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
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
        )
        from baserow.core.trash.registries import trash_item_type_registry

        if feature_flag_is_enabled(FF_AUTOMATION):
            application_type_registry.register(AutomationApplicationType())

            object_scope_type_registry.register(AutomationObjectScopeType())
            object_scope_type_registry.register(AutomationWorkflowObjectScopeType())
            object_scope_type_registry.register(AutomationNodeObjectScopeType())

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
            action_type_registry.register(OrderAutomationNodesActionType())
            action_type_registry.register(DuplicateAutomationNodeActionType())
            action_type_registry.register(ReplaceAutomationNodeActionType())

            action_scope_registry.register(WorkflowActionScopeType())

            automation_node_type_registry.register(LocalBaserowCreateRowNodeType())
            automation_node_type_registry.register(LocalBaserowUpdateRowNodeType())
            automation_node_type_registry.register(LocalBaserowDeleteRowNodeType())
            automation_node_type_registry.register(LocalBaserowGetRowNodeType())
            automation_node_type_registry.register(LocalBaserowListRowsNodeType())
            automation_node_type_registry.register(LocalBaserowAggregateRowsNodeType())
            automation_node_type_registry.register(CoreHttpRequestNodeType())
            automation_node_type_registry.register(CoreSMTPEmailNodeType())
            automation_node_type_registry.register(
                LocalBaserowRowsCreatedNodeTriggerType()
            )
            automation_node_type_registry.register(
                LocalBaserowRowsUpdatedNodeTriggerType()
            )
            automation_node_type_registry.register(
                LocalBaserowRowsDeletedNodeTriggerType()
            )

            from baserow.contrib.automation.data_providers.data_provider_types import (
                PreviousNodeProviderType,
            )
            from baserow.contrib.automation.data_providers.registries import (
                automation_data_provider_type_registry,
            )

            automation_data_provider_type_registry.register(PreviousNodeProviderType())

            from baserow.contrib.automation.nodes.permission_manager import (
                AutomationNodePermissionManager,
            )
            from baserow.contrib.automation.workflows.permission_manager import (
                AutomationWorkflowPermissionManager,
            )
            from baserow.core.registries import permission_manager_type_registry

            permission_manager_type_registry.register(
                AutomationWorkflowPermissionManager()
            )
            permission_manager_type_registry.register(AutomationNodePermissionManager())

            # The signals must always be imported last because they use
            # the registries which need to be filled first.
            import baserow.contrib.automation.nodes.ws.signals  # noqa: F403, F401
            import baserow.contrib.automation.workflows.signals  # noqa: F403, F401
            import baserow.contrib.automation.workflows.ws.signals  # noqa: F403, F401
