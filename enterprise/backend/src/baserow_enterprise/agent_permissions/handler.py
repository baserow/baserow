from django.contrib.auth.models import AbstractUser
from django.db.models import Prefetch, QuerySet

from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.models import AgentApplication
from baserow.core.models import UserProfile, Workspace
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.teams.handler import TeamHandler
from baserow_enterprise.teams.subjects import TeamSubjectType

from .exceptions import AgentRuleLeavesNoApprover
from .models import DEFAULT_ROLE, AgentParticipationRule


class AgentParticipationHandler:
    def _get_rules_queryset(
        self, agent: AgentApplication
    ) -> QuerySet[AgentParticipationRule]:
        """
        :param agent: The agent, with its workspace.
        :return: The agent's rules, with their people and teams prefetched, ready
            to be serialized.
        """

        return AgentParticipationRule.objects.filter(agent=agent).prefetch_related(
            Prefetch("users", queryset=UserSubjectType().get_queryset()),
            Prefetch(
                "teams",
                queryset=TeamHandler()
                .get_teams_queryset()
                .filter(workspace=agent.workspace),
            ),
        )

    def get_rules(
        self, agent: AgentApplication
    ) -> dict[str, AgentParticipationRule | None]:
        """
        :param agent: The agent to read, with its workspace.
        :return: The stored rule of each capability, with the people and teams
            still in the workspace, or None where its default applies.
        """

        rules = {rule.capability: rule for rule in self._get_rules_queryset(agent)}
        return {
            capability: rules.get(capability)
            for capability in AgentParticipationRule.Capability.values
        }

    def update_rule(
        self,
        agent: AgentApplication,
        capability: str,
        role: str,
        user_ids: set[int],
        team_ids: set[int],
    ) -> AgentParticipationRule | None:
        """
        Replace the rule of one capability. Saving its default role removes it.

        :param agent: The agent, locked until the transaction ends.
        :param capability: The capability the rule controls.
        :param role: The lowest role allowed, `CUSTOM` or `NOBODY`.
        :param user_ids: The people of a `CUSTOM` rule.
        :param team_ids: The teams of a `CUSTOM` rule.
        :raises ValidationError: When the capability is unknown, or the people and
            teams don't fit the role or the workspace.
        :raises AgentRuleLeavesNoApprover: When nobody could approve tool calls.
        :return: The saved rule, as `get_rules` returns it, or None when the
            default applies.
        """

        if capability not in AgentParticipationRule.Capability.values:
            raise ValidationError({"capability": "Unknown permission."})
        if capability == AgentParticipationRule.Capability.APPROVE and role == "NOBODY":
            raise AgentRuleLeavesNoApprover()
        if bool(user_ids or team_ids) != (role == "CUSTOM"):
            raise ValidationError(
                {"subjects": "Choose people or teams for a custom rule."}
            )
        users = (
            UserSubjectType()
            .get_queryset()
            .filter(
                id__in=user_ids,
                workspaceuser__workspace=agent.workspace,
                profile__user_type=UserProfile.UserType.HUMAN,
            )
        )
        teams = (
            TeamSubjectType()
            .get_queryset()
            .filter(id__in=team_ids, workspace=agent.workspace)
        )
        if users.count() != len(user_ids) or teams.count() != len(team_ids):
            raise ValidationError(
                {"subjects": "Choose people and teams in this workspace."}
            )
        if role == DEFAULT_ROLE[capability]:
            AgentParticipationRule.objects.filter(
                agent=agent, capability=capability
            ).delete()
            return None
        rule, _ = AgentParticipationRule.objects.update_or_create(
            agent=agent, capability=capability, defaults={"role": role}
        )
        rule.users.set(users)
        rule.teams.set(teams)
        return self._get_rules_queryset(agent).get(pk=rule.pk)

    def get_named_users(self, rule: AgentParticipationRule) -> list[AbstractUser]:
        """
        :param rule: A `CUSTOM` rule, as `get_rules` returns it.
        :return: The people the rule names, directly or as members of its teams.
        """

        users = {user.id: user for user in rule.users.all()}
        for team in rule.teams.all():
            for user in TeamSubjectType().get_users_included_in_subject(team):
                users[user.id] = user
        return list(users.values())

    def remove_member(self, workspace_id: int, user_id: int) -> None:
        """
        Take a person who left a workspace out of the rules of its agents, as
        their role assignments and team memberships are.

        :param workspace_id: The id of the workspace the person left.
        :param user_id: The id of the person.
        """

        AgentParticipationRule.users.through.objects.filter(
            user_id=user_id,
            agentparticipationrule__agent__workspace_id=workspace_id,
        ).delete()

    def list_subject_options(
        self,
        workspace: Workspace,
        search: str,
        exclude_user_ids: list[int],
        exclude_team_ids: list[int],
    ) -> QuerySet:
        """
        :param workspace: The workspace of the agent.
        :param search: Only people and teams whose name contains it.
        :param exclude_user_ids: People already chosen.
        :param exclude_team_ids: Teams already chosen.
        :return: The people and teams a `CUSTOM` rule can name, by name.
        """

        users = (
            UserSubjectType()
            .get_options_queryset(workspace, search, exclude_user_ids)
            .filter(subject_user_type=UserProfile.UserType.HUMAN)
        )
        teams = TeamSubjectType().get_options_queryset(
            workspace, search, exclude_team_ids
        )
        return users.union(teams).order_by("subject_name", "subject_type", "subject_id")
