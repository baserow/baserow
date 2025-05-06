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
            UpdateAutomationNodeActionType,
        )
        from baserow.contrib.automation.nodes.node_types import (
            LocalBaserowCreateRowNodeType,
            LocalBaserowRowCreatedNodeType,
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
        )
        from baserow.contrib.automation.workflows.object_scopes import (
            AutomationWorkflowObjectScopeType,
        )
        from baserow.contrib.automation.workflows.operations import (
            CreateAutomationWorkflowOperationType,
            DeleteAutomationWorkflowOperationType,
            DuplicateAutomationWorkflowOperationType,
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
            operation_type_registry.register(ListAutomationNodeOperationType())
            operation_type_registry.register(CreateAutomationNodeOperationType())
            operation_type_registry.register(UpdateAutomationNodeOperationType())
            operation_type_registry.register(ReadAutomationNodeOperationType())
            operation_type_registry.register(DeleteAutomationNodeOperationType())
            operation_type_registry.register(RestoreAutomationNodeOperationType())
            operation_type_registry.register(DuplicateAutomationNodeOperationType())
            operation_type_registry.register(OrderAutomationNodeOperationType())

            job_type_registry.register(DuplicateAutomationWorkflowJobType())

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

            action_scope_registry.register(WorkflowActionScopeType())

            automation_node_type_registry.register(LocalBaserowCreateRowNodeType())
            automation_node_type_registry.register(LocalBaserowRowCreatedNodeType())

            # The signals must always be imported last because they use
            # the registries which need to be filled first.
            import baserow.contrib.automation.nodes.ws.signals  # noqa: F403, F401
            import baserow.contrib.automation.workflows.signals  # noqa: F403, F401
            import baserow.contrib.automation.workflows.ws.signals  # noqa: F403, F401
