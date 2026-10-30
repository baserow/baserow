from django.db.models import Q, QuerySet

from baserow.core.models import (
    Application,
    Workspace,
    WorkspaceInvitation,
    WorkspaceInvitationLink,
    WorkspaceUser,
)
from baserow.core.registries import ObjectScopeType, object_scope_type_registry


class CoreObjectScopeType(ObjectScopeType):
    model_class = type(None)
    type = "core"

    def get_filter_for_scope_type(self, scope_type, scopes):
        raise TypeError("The given type is not handled.")


class WorkspaceObjectScopeType(ObjectScopeType):
    type = "workspace"
    model_class = Workspace

    def get_filter_for_scope_type(self, scope_type, scopes):
        raise TypeError("The given type is not handled.")


class ApplicationObjectScopeType(ObjectScopeType):
    type = "application"
    model_class = Application

    def get_parent_scope(self):
        return object_scope_type_registry.get("workspace")

    def get_base_queryset(self, include_trash: bool = False) -> QuerySet:
        return super().get_base_queryset(include_trash).filter(workspace__isnull=False)

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related("workspace")

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(workspace__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")


class WorkspaceInvitationObjectScopeType(ObjectScopeType):
    type = "workspace_invitation"
    model_class = WorkspaceInvitation

    def get_parent_scope(self):
        return object_scope_type_registry.get("workspace")

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related("workspace")

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(workspace__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")


class WorkspaceInvitationLinkObjectScopeType(ObjectScopeType):
    type = "workspace_invitation_link"
    model_class = WorkspaceInvitationLink

    def get_parent_scope(self):
        return object_scope_type_registry.get("workspace")

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related("workspace")

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(workspace__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")


class WorkspaceUserObjectScopeType(ObjectScopeType):
    type = "workspace_user"
    model_class = WorkspaceUser

    def get_parent_scope(self):
        return object_scope_type_registry.get("workspace")

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related("workspace")

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(workspace__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")
