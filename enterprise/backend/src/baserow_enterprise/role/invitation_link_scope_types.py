from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser
from django.db.models import prefetch_related_objects

from baserow.core.models import Application, WorkspaceInvitationLink
from baserow.core.registries import InvitationLinkScopeType
from baserow.core.trash.handler import TrashHandler
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import RBAC
from baserow_premium.license.handler import LicenseHandler

from .constants import NO_ROLE_LOW_PRIORITY_ROLE_UID, ROLE_ASSIGNABLE_OBJECT_MAP
from .handler import RoleAssignmentHandler

# The parents of each kind of object, up to the workspace, that are loaded with
# the objects of many links at once, so that checking whether one of them is
# trashed doesn't query them link by link.
SCOPE_PARENT_LOOKUPS = {
    "application": "workspace",
    "database_table": "database__workspace",
    "database_view": "table__database__workspace",
}


class RoleInvitationLinkScopeType(InvitationLinkScopeType):
    """
    Lets an invitation link give a role on an application, a table or a view through
    a role assignment, like the role a member is given on it in the share dialog.
    One is registered for every object scope type a role can be assigned on.
    """

    def __init__(self, scope_type_name: str):
        self.type = scope_type_name
        super().__init__()

    def _is_scope_usable(self, scope) -> bool:
        return (
            scope is not None
            and RoleAssignmentHandler().is_supported_invitation_link_scope(scope)
            and not TrashHandler.item_has_a_trashed_parent(scope, check_item_also=True)
        )

    def is_usable(self, invitation_link: WorkspaceInvitationLink) -> bool:
        if not LicenseHandler.workspace_has_feature(RBAC, invitation_link.workspace):
            return False
        return self._is_scope_usable(invitation_link.scope)

    def get_usable_invitation_links(
        self, invitation_links: List[WorkspaceInvitationLink]
    ) -> List[WorkspaceInvitationLink]:
        if not invitation_links or not LicenseHandler.workspace_has_feature(
            RBAC, invitation_links[0].workspace
        ):
            return []
        scopes = [link.scope for link in invitation_links if link.scope is not None]
        parent_lookup = SCOPE_PARENT_LOOKUPS.get(self.type)
        if parent_lookup:
            prefetch_related_objects(scopes, parent_lookup)
        return [link for link in invitation_links if self._is_scope_usable(link.scope)]

    def get_newcomer_permissions(self, invitation_link: WorkspaceInvitationLink) -> str:
        return NO_ROLE_LOW_PRIORITY_ROLE_UID

    def get_raised_role(
        self, user: AbstractUser, invitation_link: WorkspaceInvitationLink
    ):
        return RoleAssignmentHandler().get_role_raised_by_invitation_link(
            user, invitation_link
        )

    def give_role(self, user: AbstractUser, invitation_link: WorkspaceInvitationLink):
        handler = RoleAssignmentHandler()
        handler.assign_role(
            user,
            invitation_link.workspace,
            role=handler.get_role_by_uid(invitation_link.permissions),
            scope=invitation_link.scope,
        )

    def get_manage_permission_checks(
        self, user: AbstractUser, invitation_link: WorkspaceInvitationLink
    ) -> List[PermissionCheck]:
        # The same check as `RoleAssignmentHandler.check_scoped_invitation_permissions`
        # does before a link is changed or deleted.
        return [
            PermissionCheck(
                user,
                ROLE_ASSIGNABLE_OBJECT_MAP[self.type]["UPDATE"],
                invitation_link.scope,
            )
        ]

    def get_scope_data(
        self, invitation_links: List[WorkspaceInvitationLink]
    ) -> Dict[int, Dict[str, Any]]:
        scope_data = super().get_scope_data(invitation_links)
        for invitation_link in invitation_links:
            scope = invitation_link.scope
            if isinstance(scope, Application):
                # The kind of application, like "database", which the frontend
                # shows the object as.
                scope_data[invitation_link.id]["type"] = scope.get_type().type
            elif self.type == "database_view":
                # Tells apart the views of the same name in different tables.
                scope_data[invitation_link.id]["table_name"] = scope.table.name
        return scope_data
