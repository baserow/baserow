from django.apps import AppConfig

from baserow.core.feature_flags import FF_AUTOMATION, feature_flag_is_enabled


class AutomationConfig(AppConfig):
    name = "baserow.contrib.automation"

    def ready(self):
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
        )

        from baserow.contrib.automation.application_types import AutomationApplicationType
        from baserow.contrib.automation.object_scopes import AutomationObjectScopeType
        from baserow.contrib.automation.workflows.operations import (
            CreateWorkflowOperationType,
            DeleteWorkflowOperationType,
            DuplicateWorkflowOperationType,
            ReadWorkflowOperationType,
            UpdateWorkflowOperationType,
        )
        

        if feature_flag_is_enabled(FF_AUTOMATION):
            application_type_registry.register(AutomationApplicationType())

            object_scope_type_registry.register(AutomationObjectScopeType())

            operation_type_registry.register(CreateWorkflowOperationType())
            operation_type_registry.register(DeleteWorkflowOperationType())
            operation_type_registry.register(DuplicateWorkflowOperationType())
            operation_type_registry.register(ReadWorkflowOperationType())
            operation_type_registry.register(UpdateWorkflowOperationType())

