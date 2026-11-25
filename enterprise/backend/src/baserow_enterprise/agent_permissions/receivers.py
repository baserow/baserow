from django.dispatch import receiver

from baserow.core.models import WorkspaceUser
from baserow.core.signals import workspace_user_deleted

from .handler import AgentParticipationHandler


@receiver(workspace_user_deleted)
def remove_left_member_from_participation_rules(
    sender, workspace_user: WorkspaceUser, **kwargs
) -> None:
    # The signal's user is who removed the member, not always the member.
    AgentParticipationHandler().remove_member(
        workspace_user.workspace_id, workspace_user.user_id
    )
