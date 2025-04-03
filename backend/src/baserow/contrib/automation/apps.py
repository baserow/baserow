from django.apps import AppConfig

from baserow.core.feature_flags import FF_AUTOMATION, feature_flag_is_enabled


class AutomationConfig(AppConfig):
    name = "baserow.contrib.automation"

    def ready(self):
        from baserow.contrib.automation.application_types import (
            AutomationApplicationType,
        )
        from baserow.contrib.automation.object_scopes import AutomationObjectScopeType
        from baserow.contrib.automation.operations import (
            OrderAutomationWorkflowsOperationType,
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
            UpdateAutomationWorkflowOperationType,
        )
        from baserow.core.jobs.registries import job_type_registry
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
        )

        if feature_flag_is_enabled(FF_AUTOMATION):
            application_type_registry.register(AutomationApplicationType())

            object_scope_type_registry.register(AutomationObjectScopeType())
            object_scope_type_registry.register(AutomationWorkflowObjectScopeType())

            operation_type_registry.register(CreateAutomationWorkflowOperationType())
            operation_type_registry.register(DeleteAutomationWorkflowOperationType())
            operation_type_registry.register(DuplicateAutomationWorkflowOperationType())
            operation_type_registry.register(ReadAutomationWorkflowOperationType())
            operation_type_registry.register(UpdateAutomationWorkflowOperationType())
            operation_type_registry.register(OrderAutomationWorkflowsOperationType())

            job_type_registry.register(DuplicateAutomationWorkflowJobType())
