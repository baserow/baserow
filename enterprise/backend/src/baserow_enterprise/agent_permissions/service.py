from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import QuerySet

from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.service import AgentService
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.signals import application_pending_count_updated
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.features import RBAC
from baserow_enterprise.signals import agent_participation_rule_updated
from baserow_enterprise.teams.subjects import TeamSubjectType
from baserow_premium.license.handler import LicenseHandler

from .handler import AgentParticipationHandler
from .models import AgentParticipationRule


class AgentParticipationService:
    def __init__(self):
        self.handler = AgentParticipationHandler()

    def _get_agent(
        self,
        user: AbstractUser,
        agent_id: int,
        update: bool = False,
        lock: bool = False,
    ) -> AgentApplication:
        """
        :param user: The user asking.
        :param agent_id: The id of the agent.
        :param update: Whether the user changes the rules, which needs the access
            of a configuration update.
        :param lock: Whether to lock the agent until the transaction ends.
        :raises PermissionException: When the user may not read the agent's
            configuration, or update it when asked.
        :raises FeaturesNotAvailableError: When the workspace has no RBAC.
        :return: The agent, with its workspace.
        """

        operations = [ReadAgentConfigurationOperationType.type]
        if update:
            operations.append(UpdateApplicationOperationType.type)
        agent = AgentService().get_authorized_agent(
            user, agent_id, *operations, for_update=lock
        )
        LicenseHandler.raise_if_user_doesnt_have_feature(RBAC, user, agent.workspace)
        return agent

    def get_rules(
        self, user: AbstractUser, agent_id: int
    ) -> dict[str, AgentParticipationRule | None]:
        """
        :param user: The user asking.
        :param agent_id: The id of the agent.
        :return: The stored rule of each capability, or None where its default
            applies.
        """

        return self.handler.get_rules(self._get_agent(user, agent_id))

    @transaction.atomic
    def update_rule(
        self,
        user: AbstractUser,
        agent_id: int,
        capability: str,
        role: str,
        subjects: list[dict],
    ) -> AgentParticipationRule | None:
        """
        Replace the rule of one capability and tell the workspace's members to
        reload their permissions, which also changes who decides held calls.

        :param user: The user changing the rule.
        :param agent_id: The id of the agent.
        :param capability: The capability the rule controls.
        :param role: The lowest role allowed, `CUSTOM` or `NOBODY`.
        :param subjects: The people and teams of a `CUSTOM` rule, each with its
            `subject_type` and `subject_id`.
        :return: The saved rule, or None when the default applies.
        """

        agent = self._get_agent(user, agent_id, update=True, lock=True)
        ids_of = {
            subject_type: {
                subject["subject_id"]
                for subject in subjects
                if subject["subject_type"] == subject_type
            }
            for subject_type in (UserSubjectType.type, TeamSubjectType.type)
        }
        rule = self.handler.update_rule(
            agent,
            capability,
            role,
            ids_of[UserSubjectType.type],
            ids_of[TeamSubjectType.type],
        )
        agent_participation_rule_updated.send(self, agent=agent)
        application_pending_count_updated.send(self, application=agent, user_ids=None)
        return rule

    def list_subject_options(
        self,
        user: AbstractUser,
        agent_id: int,
        search: str,
        exclude_user_ids: list[int],
        exclude_team_ids: list[int],
    ) -> QuerySet:
        """
        :param user: The user choosing.
        :param agent_id: The id of the agent.
        :param search: Only people and teams whose name contains it.
        :param exclude_user_ids: People already chosen.
        :param exclude_team_ids: Teams already chosen.
        :return: The people and teams a `CUSTOM` rule can name, by name.
        """

        agent = self._get_agent(user, agent_id, update=True)
        return self.handler.list_subject_options(
            agent.workspace, search, exclude_user_ids, exclude_team_ids
        )
