from django.db.models import Q, QuerySet

from baserow.contrib.automation.models import Automation
from baserow.core.object_scopes import (
    ApplicationObjectScopeType,
    WorkspaceObjectScopeType,
)
from baserow.core.registries import ObjectScopeType, object_scope_type_registry


class AutomationObjectScopeType(ObjectScopeType):
    type = "automation"
    model_class = Automation

    def get_parent_scope(self):
        return object_scope_type_registry.get("application")

    def get_base_queryset(self, include_trash: bool = False) -> QuerySet:
        return super().get_base_queryset(include_trash)

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related("workspace")

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(workspace__in=[s.id for s in scopes])
        if scope_type.type == ApplicationObjectScopeType.type:
            return Q(id__in=[s.id for s in scopes])
        if scope_type.type == self.type:
            return Q(id__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")
