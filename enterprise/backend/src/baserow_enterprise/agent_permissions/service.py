from typing import Any

from django.db import transaction

from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.models import AgentApplication
from baserow.core.signals import application_pending_count_updated
from baserow.core.subjects import UserSubjectType
from baserow.ws.tasks import broadcast_to_users
from baserow_enterprise.teams.subjects import TeamSubjectType

from .models import DEFAULT_ROLE, AgentParticipationRule, is_allowed_rule


def update_rule(
    agent: AgentApplication,
    capability: str,
    role: str,
    selected: list[dict[str, Any]],
) -> AgentParticipationRule | None:
    """
    Replace one rule while the calling transaction holds the agent lock. Saving
    the capability's default role removes the rule.

    :param agent: The agent the rule belongs to.
    :param capability: The capability the rule controls.
    :param role: The lowest role allowed, `CUSTOM` or `NOBODY`.
    :param selected: The users and teams of a `CUSTOM` rule.
    :raises ValidationError: When the capability is unknown, nobody could
        approve tool calls, or the people and teams don't fit the role.
    :return: The saved rule, or None when the default applies.
    """

    if capability not in AgentParticipationRule.Capability.values:
        raise ValidationError({"capability": "Unknown permission."})
    if not is_allowed_rule(capability, role):
        raise ValidationError({"role": "Someone must be able to approve tool calls."})
    if bool(selected) != (role == "CUSTOM"):
        raise ValidationError({"subjects": "Choose people or teams for a custom rule."})
    user_ids = {
        s["subject_id"] for s in selected if s["subject_type"] == UserSubjectType.type
    }
    team_ids = {
        s["subject_id"] for s in selected if s["subject_type"] == TeamSubjectType.type
    }
    users = (
        UserSubjectType()
        .get_queryset()
        .filter(
            pk__in=user_ids,
            workspaceuser__workspace=agent.workspace,
            profile__user_type="human",
        )
    )
    teams = (
        TeamSubjectType()
        .get_queryset()
        .filter(pk__in=team_ids, workspace=agent.workspace)
    )
    if users.count() != len(user_ids) or teams.count() != len(team_ids):
        raise ValidationError(
            {"subjects": "Choose people and teams in this workspace."}
        )
    if role == DEFAULT_ROLE[capability]:
        AgentParticipationRule.objects.filter(
            agent=agent, capability=capability
        ).delete()
        rule = None
    else:
        rule, _ = AgentParticipationRule.objects.update_or_create(
            agent=agent, capability=capability, defaults={"role": role}
        )
        rule.users.set(users)
        rule.teams.set(teams)
    member_ids = list(
        agent.workspace.workspaceuser_set.values_list("user_id", flat=True)
    )
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            member_ids,
            {"type": "permissions_updated", "workspace_id": agent.workspace_id},
        )
    )
    application_pending_count_updated.send(
        update_rule, application=agent, user_ids=None
    )
    return rule
