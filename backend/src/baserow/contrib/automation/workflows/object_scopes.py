from typing import Optional

from django.db.models import Q, QuerySet

from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.object_scopes import AutomationObjectScopeType
from baserow.core.object_scopes import (
    ApplicationObjectScopeType,
    WorkspaceObjectScopeType,
)
from baserow.core.registries import ObjectScopeType, object_scope_type_registry


class AutomationWorkflowObjectScopeType(ObjectScopeType):
    type = "automation_workflow"
    model_class = AutomationWorkflow

    def get_parent_scope(self) -> Optional["ObjectScopeType"]:
        return object_scope_type_registry.get("automation")

    def get_base_queryset(self, include_trash: bool = False) -> QuerySet:
        return (
            super()
            .get_base_queryset(include_trash)
            .filter(automation__workspace__isnull=False)
        )

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related(
            "automation__workspace"
        )

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(automation__workspace__in=[s.id for s in scopes])

        if (
            scope_type.type == AutomationObjectScopeType.type
            or scope_type.type == ApplicationObjectScopeType.type
        ):
            return Q(automation__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")
