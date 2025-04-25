from typing import Optional

from django.db.models import Q, QuerySet

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.object_scopes import AutomationObjectScopeType
from baserow.contrib.automation.workflows.object_scopes import (
    AutomationWorkflowObjectScopeType,
)
from baserow.core.object_scopes import (
    ApplicationObjectScopeType,
    WorkspaceObjectScopeType,
)
from baserow.core.registries import ObjectScopeType, object_scope_type_registry


class AutomationNodeObjectScopeType(ObjectScopeType):
    type = "automation_node"
    model_class = AutomationNode

    def get_parent_scope(self) -> Optional["ObjectScopeType"]:
        return object_scope_type_registry.get("automation_workflow")

    def get_base_queryset(self, include_trash: bool = False) -> QuerySet:
        return (
            super()
            .get_base_queryset(include_trash)
            .filter(workflow__automation__workspace__isnull=False)
        )

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related(
            "workflow__automation__workspace"
        )

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(workflow__automation__workspace__in=[s.id for s in scopes])

        if (
            scope_type.type == AutomationObjectScopeType.type
            or scope_type.type == ApplicationObjectScopeType.type
        ):
            return Q(workflow__automation__in=[s.id for s in scopes])

        if (
            scope_type.type == AutomationWorkflowObjectScopeType.type
            or scope_type.type == ApplicationObjectScopeType.type
        ):
            return Q(workflow__id__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")
