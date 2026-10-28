from django.contrib.auth.models import AbstractUser

from baserow.core.models import WorkspaceInvitationLink
from baserow.core.registries import InvitationLinkScopeType
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.features import RBAC
from baserow_premium.license.handler import LicenseHandler

from .constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from .handler import RoleAssignmentHandler


class RoleInvitationLinkScopeType(InvitationLinkScopeType):
    """
    Lets an invitation link give a role on an application, a table or a view through
    a role assignment, like the role a member is given on it in the share dialog.
    One is registered for every object scope type a role can be assigned on.
    """

    def __init__(self, scope_type_name: str):
        self.type = scope_type_name
        super().__init__()

    def is_usable(self, invitation_link: WorkspaceInvitationLink) -> bool:
        if not LicenseHandler.workspace_has_feature(RBAC, invitation_link.workspace):
            return False
        scope = invitation_link.scope
        return scope is not None and not TrashHandler.item_has_a_trashed_parent(
            scope, check_item_also=True
        )

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
