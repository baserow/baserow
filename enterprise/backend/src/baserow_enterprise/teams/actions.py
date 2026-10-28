import dataclasses
from typing import Dict, List, Optional, Union

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.models import Workspace
from baserow_enterprise.models import Team, TeamSubject
from baserow_enterprise.role.models import Role
from baserow_enterprise.scopes import TeamsActionScopeType
from baserow_enterprise.teams.handler import TeamHandler

TEAM_CONTEXT = _('in team "%(team_name)s" (%(team_id)s) ')

# None of the team actions are undoable, like workspace invitations: undoing them
# would add or remove someone's access without asking.


class CreateTeamActionType(ActionType):
    type = "create_team"
    description = ActionTypeDescription(
        _("Create team"),
        _('Team "%(name)s" (%(team_id)s) created.'),
    )
    analytics_params = [
        "team_id",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        name: str
        team_id: int
        workspace_id: int
        subjects: List[Dict]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        name: str,
        workspace: Workspace,
        subjects: Optional[List[Dict]] = None,
        default_role: Optional[Role] = None,
    ) -> Team:
        """
        Creates a new team for an existing user. See
        baserow_enterprise.teams.handler.TeamHandler.create_team
        for more details.

        :param user: The user creating the team.
        :param name: The name to give the team.
        :param workspace: The workspace to create the team in.
        :param subjects: An array of subject ID/type objects.
        :param default_role: The default role to apply to the workspace.
        """

        if subjects is None:
            subjects = []

        team = TeamHandler().create_team(user, name, workspace, subjects, default_role)

        cls.register_action(
            user=user,
            params=cls.Params(team.name, team.id, workspace.id, subjects),
            scope=cls.scope(team.workspace_id),
            workspace=workspace,
        )
        return team

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return TeamsActionScopeType.value(workspace_id)


class UpdateTeamActionType(ActionType):
    type = "update_team"
    description = ActionTypeDescription(
        _("Update team"),
        _('Team "%(name)s" (%(team_id)s) updated.'),
    )
    analytics_params = [
        "team_id",
        "workspace_id",
        "original_default_role_uid",
        "default_role_uid",
    ]

    @dataclasses.dataclass
    class Params:
        team_id: int
        original_name: str
        name: str
        workspace_id: int
        subjects: List[Dict]
        original_default_role_uid: Union[str, None]
        default_role_uid: Union[str, None]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        team: Team,
        name: str,
        subjects: Optional[List[Dict]] = None,
        default_role: Optional[Role] = None,
    ) -> Team:
        """
        Updates an existing team instance.
        See baserow_enterprise.teams.handler.TeamHandler.update_team
            for further details.

        :param user: The user on whose behalf the team is updated.
        :param team: The team instance that needs to be updated.
        :param name: The new name of the team.
        :param subjects: An array of subject ID/type objects.
        :param default_role: The default role to apply to the workspace.
        :raises ValueError: If one of the provided parameters is invalid.
        :return: The updated team instance.
        """

        if subjects is None:
            subjects = []

        # Stash the original name and default role.
        original_name = team.name
        original_default_role_uid = team.default_role_uid

        default_role_uid = getattr(default_role, "uid", None)

        team = TeamHandler().update_team(user, team, name, subjects, default_role)

        cls.register_action(
            user=user,
            params=cls.Params(
                team.id,
                original_name,
                name,
                team.workspace_id,
                subjects,
                original_default_role_uid,
                default_role_uid,
            ),
            scope=cls.scope(team.workspace_id),
            workspace=team.workspace,
        )

        return team

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return TeamsActionScopeType.value(workspace_id)


class DeleteTeamActionType(ActionType):
    type = "delete_team"
    description = ActionTypeDescription(
        _("Delete team"),
        _('Team "%(team_name)s" (%(team_id)s) deleted.'),
    )
    analytics_params = [
        "team_id",
    ]

    @dataclasses.dataclass
    class Params:
        team_id: int
        team_name: str

    @classmethod
    def do(cls, user: AbstractUser, team: Team) -> None:
        """
        Deletes an existing team instance if the user has access to the
        related workspace. The `team_deleted` signal is also called. See
        baserow_enterprise.teams.handler.TeamHandler.delete_team for further details.
        The team can still be restored from the trash.

        :param user: The user on whose behalf the team is deleted.
        :param team: The team instance that needs to be deleted.
        """

        TeamHandler().delete_team(user, team)

        cls.register_action(
            user=user,
            params=cls.Params(team.id, team.name),
            scope=cls.scope(team.workspace_id),
            workspace=team.workspace,
        )

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return TeamsActionScopeType.value(workspace_id)


class CreateTeamSubjectActionType(ActionType):
    type = "create_team_subject"
    description = ActionTypeDescription(
        _("Create team subject"), _("Subject (%(subject_id)s) created"), TEAM_CONTEXT
    )
    analytics_params = [
        "team_id",
        "subject_id",
        "subject_subject_type_natural_key",
    ]

    @dataclasses.dataclass
    class Params:
        team_id: int
        team_name: str
        subject_id: int  # TeamSubject PK
        subject_lookup: Dict[
            str, Union[str, int]
        ]  # User.email | TeamSubject.subject_id
        subject_subject_type_natural_key: int  # TeamSubject.subject_type natural key

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        subject_lookup: Dict[str, Union[str, int]],
        subject_type: str,
        team: Team,
    ) -> TeamSubject:
        """
        Creates a new subject for an existing team. See
        baserow_enterprise.teams.handler.TeamHandler.create_subject
        for more details.

        :param user: The user creating the team.
        :param subject_lookup: The subject's identifier. A dictionary pointing to
            the subject's ID/PK or an email address is required.
        :param subject_type: The subject's content type natural key.
        :param team: The team to invite the subject to.
        """

        subject = TeamHandler().create_subject(user, subject_lookup, subject_type, team)

        cls.register_action(
            user=user,
            params=cls.Params(
                team.id, team.name, subject.id, subject_lookup, subject_type
            ),
            scope=cls.scope(team.workspace_id),
            workspace=team.workspace,
        )
        return subject

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return TeamsActionScopeType.value(workspace_id)


class DeleteTeamSubjectActionType(ActionType):
    type = "delete_team_subject"
    description = ActionTypeDescription(
        _("Delete team subject"),
        _("Subject (%(subject_id)s) deleted"),
        TEAM_CONTEXT,
    )
    analytics_params = [
        "team_id",
        "subject_id",
        "subject_subject_id",
        "subject_subject_type_natural_key",
    ]

    @dataclasses.dataclass
    class Params:
        team_id: int
        team_name: str
        subject_id: int  # TeamSubject PK
        subject_subject_id: int  # TeamSubject.subject_id
        subject_subject_type_natural_key: int  # TeamSubject.subject_type natural key

    @classmethod
    def do(cls, user: AbstractUser, subject: TeamSubject) -> None:
        """
        Deletes an existing subject instance if the user has access to the
        related workspace. The `team_subject_deleted` signal is also called. See
        baserow_enterprise.teams.handler.TeamHandler.delete_team_subject for
        further details.

        :param user: The user on whose behalf the team is deleted.
        :param team: The team instance that needs to be deleted.
        """

        subject_id = subject.id
        TeamHandler().delete_subject(user, subject)

        cls.register_action(
            user=user,
            params=cls.Params(
                subject.team_id,
                subject.team.name,
                subject_id,
                subject.subject_id,
                subject.subject_type_natural_key,
            ),
            scope=cls.scope(subject.team.workspace_id),
            workspace=subject.team.workspace,
        )

    @classmethod
    def scope(cls, team_id: int) -> ActionScopeStr:
        return TeamsActionScopeType.value(team_id)
