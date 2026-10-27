from django.db.models import Q

from baserow.core.registries import ObjectScopeType, object_scope_type_registry

from .models import DashboardFilter


class DashboardFilterObjectScopeType(ObjectScopeType):
    type = "dashboard_filter"
    model_class = DashboardFilter

    def get_parent_scope(self):
        return object_scope_type_registry.get("dashboard")

    def get_base_queryset(self, include_trash=False):
        return (
            super()
            .get_base_queryset(include_trash)
            .filter(dashboard__workspace__isnull=False)
        )

    def get_enhanced_queryset(self, include_trash=False):
        return self.get_base_queryset(include_trash).select_related(
            "dashboard__workspace"
        )

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == "workspace":
            return Q(dashboard__workspace__in=scopes)
        if scope_type.type in ("dashboard", "application"):
            return Q(dashboard__in=scopes)
        raise TypeError("The given type is not handled.")
