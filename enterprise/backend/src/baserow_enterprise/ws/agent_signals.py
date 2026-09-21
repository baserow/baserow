from django.db import transaction
from django.dispatch import receiver

from baserow.core.agents.handler import AgentHandler
from baserow.core.agents.signals import agent_updated
from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.models import Agent
from baserow_enterprise.signals import (
    team_deleted,
    team_restored,
    team_subject_created,
    team_subject_deleted,
    team_subject_restored,
    team_updated,
)
from baserow_enterprise.teams.models import TeamSubject


def notify_agents_after_team_change(workspace, agent_ids):
    """Send committed team summaries through the permission-filtered agent event."""

    def notify():
        # Reload after commit: cached annotations and intermediate membership sets
        # must not be sent to clients. Trashed agents need no list update.
        agents = AgentHandler().get_queryset(workspace).filter(id__in=agent_ids)
        for agent in agents:
            # Team responses do not update the caller's agent store, so include
            # the originating connection in this secondary event too.
            agent_updated.send(Agent, agent=agent, user=None)

    transaction.on_commit(notify)


@receiver(team_subject_created)
@receiver(team_subject_deleted)
@receiver(team_subject_restored)
def agent_team_membership_changed(sender, subject, **kwargs):
    """Refresh an agent when its team membership is added, removed or restored."""

    if subject.subject_type_id == AgentSubjectType().get_content_type().id:
        notify_agents_after_team_change(subject.team.workspace, [subject.subject_id])


@receiver(team_updated)
@receiver(team_deleted)
@receiver(team_restored)
def agent_team_changed(sender, team, **kwargs):
    """Refresh member agents when a team is renamed, trashed or restored."""

    agent_ids = list(
        TeamSubject.objects_and_trash.filter(
            team=team, subject_type=AgentSubjectType().get_content_type()
        )
        .values_list("subject_id", flat=True)
        .distinct()
    )
    if agent_ids:
        notify_agents_after_team_change(team.workspace, agent_ids)
