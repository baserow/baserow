from dataclasses import asdict, dataclass

from baserow.core.models import Application
from baserow.core.notifications.helpers import notify_admins_in_workspace
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
        """
        Notifies the active workspace admins that an automatic snapshot of the
        provided application failed.

        :param schedule: The schedule that ran.
        :param application: The application the snapshot was for.
        :param error: The message of the failure, safe to show to the admins.
        :return: The created notification recipients.
        """

        data = AutomaticSnapshotFailedData(
            workspace_id=schedule.workspace_id,
            schedule_id=schedule.id,
            application_id=application.id,
            application_name=application.name,
            error=error,
        )
        return notify_admins_in_workspace(schedule.workspace, cls.type, asdict(data))
