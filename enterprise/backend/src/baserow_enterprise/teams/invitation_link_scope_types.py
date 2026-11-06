from django.contrib.auth.models import AbstractUser

from baserow.core.models import WorkspaceInvitationLink
from baserow.core.registries import InvitationLinkScopeType
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.features import TEAMS
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_premium.license.handler import LicenseHandler

from .models import Team
from .object_scopes import TeamObjectScopeType


class TeamInvitationLinkScopeType(InvitationLinkScopeType):
    """
    Lets an invitation link add people to a team. A team gives its own role to its
    members, so the link has no role: newcomers join the workspace without a role
    of their own, which lets the role of the team apply, and members of the
    workspace who aren't in the team yet are added to it.
    """

    type = TeamObjectScopeType.type

    def is_usable(self, invitation_link: WorkspaceInvitationLink) -> bool:
        if not LicenseHandler.workspace_has_feature(TEAMS, invitation_link.workspace):
            return False
        # The scope is loaded without the trash filter, so a trashed team is
        # returned too.
        team = invitation_link.scope
        return team is not None and not team.trashed

    def get_newcomer_permissions(self, invitation_link: WorkspaceInvitationLink) -> str:
        return NO_ROLE_LOW_PRIORITY_ROLE_UID

    def get_raised_role(
        self, user: AbstractUser, invitation_link: WorkspaceInvitationLink
    ):
        # A team has no role per member that a link could raise.
        return None

    def _is_in_team(self, user: AbstractUser, team: Team) -> bool:
        from .handler import TeamHandler

        return TeamHandler().get_teamsubject_subject_qs(user).filter(team=team).exists()

    def adds_member(
        self, user: AbstractUser, invitation_link: WorkspaceInvitationLink
    ) -> bool:
        return not self._is_in_team(user, invitation_link.scope)

    def give_role(self, user: AbstractUser, invitation_link: WorkspaceInvitationLink):
        from .handler import TeamHandler

        # Locking the team makes concurrent joins of the same person wait, so they
        # are added only once.
        team = (
            Team.objects.select_for_update(of=("self",))
            .select_related("workspace")
            .get(id=invitation_link.scope_id)
        )
        if self._is_in_team(user, team):
            return

        TeamHandler().create_subject(user, {"id": user.id}, UserSubjectType.type, team)
