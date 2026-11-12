from django.db import transaction
from django.dispatch import receiver

from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.signals import identity_updated
from baserow.core.models import User
from baserow.core.subjects import UserSubjectType
from baserow.core.user.identity import is_identity
from baserow_enterprise.signals import (
    team_deleted,
    team_restored,
    team_subject_created,
    team_subject_deleted,
    team_updated,
)
from baserow_enterprise.teams.models import TeamSubject


def notify_identities_after_team_change(workspace, identity_ids):
    """Send committed team summaries through the permission-filtered identity event."""

    def notify():
        # Reloaded after commit so clients never get an intermediate team set.
        identities = (
            IdentityHandler().get_queryset(workspace).filter(id__in=identity_ids)
        )
        for identity in identities:
            # No user: the caller's own tab needs it, team responses skip identities.
            identity_updated.send(User, identity=identity, user=None)

    transaction.on_commit(notify)


@receiver(team_subject_created)
@receiver(team_subject_deleted)
def identity_team_membership_changed(sender, subject, **kwargs):
    """Refresh an identity when its team membership is added or removed."""

    if (
        subject.subject_type_id == UserSubjectType().get_content_type().id
        and is_identity(subject.subject)
    ):
        notify_identities_after_team_change(
            subject.team.workspace, [subject.subject_id]
        )


@receiver(team_updated)
@receiver(team_deleted)
@receiver(team_restored)
def identity_team_changed(sender, team, **kwargs):
    """Refresh member identities when a team is renamed, trashed or restored."""

    identity_ids = list(
        TeamSubject.objects_and_trash.filter(
            team=team, subject_type=UserSubjectType().get_content_type()
        )
        .values_list("subject_id", flat=True)
        .distinct()
    )
    if identity_ids:
        notify_identities_after_team_change(team.workspace, identity_ids)
