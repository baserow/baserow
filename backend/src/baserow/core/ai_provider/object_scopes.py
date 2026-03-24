from django.db.models import Q

from baserow.core.ai_provider.models import AIProviderConfig
from baserow.core.object_scopes import (
    ApplicationObjectScopeType,
    WorkspaceObjectScopeType,
)
from baserow.core.registries import ObjectScopeType, object_scope_type_registry


class AIProviderConfigObjectScopeType(ObjectScopeType):
    type = "ai_provider_config"
    model_class = AIProviderConfig

    def get_parent_scope(self):
        # AIProviderConfig can live at instance, workspace, or application scope.
        # The parent varies based on the scope GFK, but for RBAC hierarchy
        # purposes we return workspace as the broadest common parent.
        return object_scope_type_registry.get("workspace")

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            from django.contrib.contenttypes.models import ContentType

            from baserow.core.models import Workspace

            workspace_ct = ContentType.objects.get_for_model(Workspace)
            scope_ids = [s.id for s in scopes]
            return Q(
                scope_content_type=workspace_ct,
                scope_object_id__in=scope_ids,
            )

        if scope_type.type == ApplicationObjectScopeType.type:
            from django.contrib.contenttypes.models import ContentType

            from baserow.core.models import Application

            app_ct = ContentType.objects.get_for_model(Application)
            scope_ids = [s.id for s in scopes]
            return Q(
                scope_content_type=app_ct,
                scope_object_id__in=scope_ids,
            )

        raise TypeError("The given type is not handled.")
