from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser
from django.db.models import prefetch_related_objects

from baserow.core.models import WorkspaceInvitationLink
from baserow.core.operations import CreateInvitationLinkWorkspaceOperationType
from baserow.core.registries import InvitationLinkScopeType
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import TEAMS
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_premium.license.handler import LicenseHandler

from .models import Team
from .object_scopes import TeamObjectScopeType
from .operations import CreateTeamSubjectOperationType


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

    def get_usable_invitation_links(
        self, invitation_links: List[WorkspaceInvitationLink]
    ) -> List[WorkspaceInvitationLink]:
        if not invitation_links or not LicenseHandler.workspace_has_feature(
            TEAMS, invitation_links[0].workspace
        ):
            return []
        teams = [link.scope for link in invitation_links if link.scope is not None]
        # The permission checks of the links go through the workspace of each team.
        prefetch_related_objects(teams, "workspace")
        return [
            link
            for link in invitation_links
            if link.scope is not None and not link.scope.trashed
        ]

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

    def get_manage_permission_checks(
        self, user: AbstractUser, invitation_link: WorkspaceInvitationLink
    ) -> List[PermissionCheck]:
        # The same checks as `TeamHandler._check_invitation_link_permissions` does
        # before a link is changed or deleted.
        return [
            PermissionCheck(
                user, CreateTeamSubjectOperationType.type, invitation_link.scope
            ),
            PermissionCheck(
                user,
                CreateInvitationLinkWorkspaceOperationType.type,
                invitation_link.workspace,
            ),
        ]

    def get_scope_data(
        self, invitation_links: List[WorkspaceInvitationLink]
    ) -> Dict[int, Dict[str, Any]]:
        from .handler import TeamHandler

        # The role the team gives its members, which is what people get through
        # its links, loaded for all the teams at once.
        default_roles = dict(
            TeamHandler()
            .get_teams_queryset()
            .filter(id__in=[link.scope_id for link in invitation_links])
            .values_list("id", "_annotated_default_role_uid")
        )
        scope_data = super().get_scope_data(invitation_links)
        for invitation_link in invitation_links:
            scope_data[invitation_link.id]["default_role"] = default_roles.get(
                invitation_link.scope_id
            )
        return scope_data
