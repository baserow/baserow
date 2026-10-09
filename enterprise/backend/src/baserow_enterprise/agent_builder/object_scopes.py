from django.db.models import Q

from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.object_scopes import (
    ApplicationObjectScopeType,
    WorkspaceObjectScopeType,
)
from baserow.core.registries import ObjectScopeType, object_scope_type_registry
from baserow_enterprise.agent_builder.models import AgentBuilder, AgentDefinition


class AgentBuilderObjectScopeType(ObjectScopeType):
    type = "agent_builder"
    model_class = AgentBuilder
    feature_flag = FF_AGENT_BUILDER

    def get_parent_scope(self):
        return object_scope_type_registry.get(ApplicationObjectScopeType.type)

    def get_base_queryset(self, include_trash=False):
        queryset = super().get_base_queryset(include_trash)
        if not feature_flag_is_enabled(FF_AGENT_BUILDER):
            return queryset.none()
        return queryset

    def get_enhanced_queryset(self, include_trash=False):
        return self.get_base_queryset(include_trash).select_related("workspace")

    def get_filter_for_scope_type(self, scope_type, scopes):
        ids = [scope.id for scope in scopes]
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(workspace__in=ids)
        if scope_type.type in (ApplicationObjectScopeType.type, self.type):
            return Q(id__in=ids)
        raise TypeError("The given type is not handled.")


class AgentObjectScopeType(ObjectScopeType):
    type = "agent_builder_agent"
    model_class = AgentDefinition
    feature_flag = FF_AGENT_BUILDER

    def get_parent_scope(self):
        return object_scope_type_registry.get(AgentBuilderObjectScopeType.type)

    def get_base_queryset(self, include_trash=False):
        queryset = (
            super()
            .get_base_queryset(include_trash)
            .filter(agent_builder__workspace__isnull=False)
        )
        if not feature_flag_is_enabled(FF_AGENT_BUILDER):
            return queryset.none()
        return queryset

    def get_enhanced_queryset(self, include_trash=False):
        return self.get_base_queryset(include_trash).select_related(
            "agent_builder__workspace"
        )

    def get_filter_for_scope_type(self, scope_type, scopes):
        ids = [scope.id for scope in scopes]
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(agent_builder__workspace__in=ids)
        if scope_type.type in (
            ApplicationObjectScopeType.type,
            AgentBuilderObjectScopeType.type,
        ):
            return Q(agent_builder__in=ids)
        raise TypeError("The given type is not handled.")
