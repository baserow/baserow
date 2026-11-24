from dataclasses import asdict, dataclass

from django.db import transaction

from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    Application,
    Workspace,
    WorkspaceUser,
)
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.notifications.registries import NotificationType

from .models import AutomaticSnapshotSchedule


@dataclass
class AutomaticSnapshotFailedData:
    workspace_id: int
    schedule_id: int
    application_id: int
    application_name: str
    error: str


class AutomaticSnapshotFailedNotificationType(NotificationType):
    type = "automatic_snapshot_failed"

    @classmethod
    def notify_admins(
        cls, schedule: AutomaticSnapshotSchedule, application: Application, error: str
    ) -> list[NotificationRecipient]:
        """Notify active workspace admins once per unread schedule/application failure."""

        with transaction.atomic():
            # Serialize duplicate checks for concurrent failures in this workspace.
            Workspace.objects.select_for_update(no_key=True).get(
                id=schedule.workspace_id
            )
            already_notified = NotificationRecipient.objects.filter(
                notification__type=cls.type,
                notification__workspace_id=schedule.workspace_id,
                notification__data__contains={
                    "schedule_id": schedule.id,
                    "application_id": application.id,
                },
                read=False,
                cleared=False,
            ).values_list("recipient_id", flat=True)
            admins = (
                WorkspaceUser.objects.filter(
                    workspace_id=schedule.workspace_id,
                    permissions=WORKSPACE_USER_PERMISSION_ADMIN,
                    user__is_active=True,
                    user__profile__to_be_deleted=False,
                )
                .exclude(user_id__in=already_notified)
                .select_related("user")
            )
            data = AutomaticSnapshotFailedData(
                workspace_id=schedule.workspace_id,
                schedule_id=schedule.id,
                application_id=application.id,
                application_name=application.name,
                error=error,
            )
            return NotificationHandler.create_direct_notification_for_users(
                notification_type=cls.type,
                recipients=[admin.user for admin in admins],
                data=asdict(data),
                sender=None,
                workspace=schedule.workspace,
            )
