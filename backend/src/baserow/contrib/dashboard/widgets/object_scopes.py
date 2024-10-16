from typing import Optional

from django.db.models import Q, QuerySet

from baserow.contrib.dashboard.object_scopes import DashboardObjectScopeType
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.core.object_scopes import (
    ApplicationObjectScopeType,
    WorkspaceObjectScopeType,
)
from baserow.core.registries import ObjectScopeType, object_scope_type_registry


class WidgetObjectScopeType(ObjectScopeType):
    type = "dashboard_widget"
    model_class = Widget

    def get_parent_scope(self) -> Optional["ObjectScopeType"]:
        return object_scope_type_registry.get("dashboard")

    def get_base_queryset(self, include_trash: bool = False) -> QuerySet:
        return (
            super()
            .get_base_queryset(include_trash)
            .filter(dashboard__workspace__isnull=False)
        )

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related(
            "dashboard__workspace"
        )

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(dashboard__workspace__in=[s.id for s in scopes])

        if (
            scope_type.type == DashboardObjectScopeType.type
            or scope_type.type == ApplicationObjectScopeType.type
        ):
            return Q(dashboard__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")
