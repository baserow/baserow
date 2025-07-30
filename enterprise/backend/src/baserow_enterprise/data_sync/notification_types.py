from dataclasses import asdict, dataclass
from typing import List, Optional

from django.conf import settings
from django.utils.translation import gettext as _

from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.notifications.registries import (
    EmailNotificationTypeMixin,
    NotificationType,
)

from .models import DEACTIVATION_REASON_LICENSE_UNAVAILABLE, PeriodicDataSyncInterval


@dataclass
class DeactivatedPeriodicDataSyncData:
    data_sync_id: int
    table_name: str
    table_id: int
    database_id: int
    deactivation_reason: Optional[str]

    @classmethod
    def from_periodic_data_sync(cls, periodic_data_sync: PeriodicDataSyncInterval):
        return cls(
            data_sync_id=periodic_data_sync.data_sync_id,
            table_name=periodic_data_sync.data_sync.table.name,
            table_id=periodic_data_sync.data_sync.table.id,
            database_id=periodic_data_sync.data_sync.table.database_id,
            deactivation_reason=periodic_data_sync.deactivation_reason,
        )


class PeriodicDataSyncDeactivatedNotificationType(
    EmailNotificationTypeMixin, NotificationType
):
    type = "periodic_data_sync_deactivated"
    has_web_frontend_route = True

    @classmethod
    def notify_authorized_user(
        cls, periodic_data_sync: PeriodicDataSyncInterval
    ) -> Optional[List[NotificationRecipient]]:
        """
        Creates a notification for the authorized user of the periodic data sync
        that was deactivated.

        :param periodic_data_sync: The periodic data sync that was deactivated.
        """

        workspace = periodic_data_sync.data_sync.table.database.workspace
        return NotificationHandler.create_direct_notification_for_users(
            notification_type=PeriodicDataSyncDeactivatedNotificationType.type,
            recipients=[periodic_data_sync.authorized_user],
            data=asdict(
                DeactivatedPeriodicDataSyncData.from_periodic_data_sync(
                    periodic_data_sync
                )
            ),
            sender=None,
            workspace=workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _("%(name)s periodic data sync has been deactivated.") % {
            "name": notification.data["table_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        deactivation_reason = notification.data.get("deactivation_reason")
        if deactivation_reason == DEACTIVATION_REASON_LICENSE_UNAVAILABLE:
            return _(
                "The periodic data sync has been disabled because the workspace "
                "no longer has a valid license for data sync features. "
                "Please update your license to restore automatic syncing."
            )
        else:
            return _(
                "The periodic data sync failed more than %(max_failures)s consecutive times "
                "and was therefore deactivated."
            ) % {
                "max_failures": settings.BASEROW_ENTERPRISE_MAX_PERIODIC_DATA_SYNC_CONSECUTIVE_ERRORS,
            }
