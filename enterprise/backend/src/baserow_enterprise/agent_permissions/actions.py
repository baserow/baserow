from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.agent.models import AgentApplication
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.teams.subjects import TeamSubjectType

from .models import AgentParticipationRule
from .service import AgentParticipationService


class UpdateAgentParticipationRuleActionType(ActionType):
    type = "update_agent_participation_rule"
    description = ActionTypeDescription(
        _("Update agent permission"),
        _('Agent "%(agent_name)s" (%(agent_id)s): "%(capability)s" set to "%(role)s"'),
    )
    analytics_params = ["agent_id", "capability", "role"]

    @dataclass
    class Params:
        agent_id: int
        agent_name: str
        capability: str
        role: str
        user_ids: list[int]
        team_ids: list[int]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        agent_id: int,
        capability: str,
        role: str,
        subjects: list[dict],
    ) -> AgentParticipationRule | None:
        """
        Replace the rule of one capability, recording who changed it and how.

        :param user: The user changing the rule.
        :param agent_id: The id of the agent.
        :param capability: The capability the rule controls.
        :param role: The lowest role allowed, `CUSTOM` or `NOBODY`.
        :param subjects: The people and teams of a `CUSTOM` rule, each with its
            `subject_type` and `subject_id`.
        :return: The saved rule, or None when the default applies.
        """

        rule = AgentParticipationService().update_rule(
            user, agent_id, capability, role, subjects
        )
        agent = AgentApplication.objects.select_related("workspace").get(id=agent_id)

        def ids_of(subject_type: str) -> list[int]:
            return sorted(
                subject["subject_id"]
                for subject in subjects
                if subject["subject_type"] == subject_type
            )

        cls.register_action(
            user,
            cls.Params(
                agent.id,
                agent.name,
                capability,
                role,
                ids_of(UserSubjectType.type),
                ids_of(TeamSubjectType.type),
            ),
            cls.scope(agent.id),
            agent.workspace,
        )
        return rule

    @classmethod
    def scope(cls, agent_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(agent_id)
