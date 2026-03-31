from dataclasses import asdict, dataclass
from typing import List, Optional
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import ngettext

from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import Notification, NotificationRecipient
from baserow.core.notifications.registries import (
    EmailNotificationTypeMixin,
    NotificationType,
)

from .models import DataScan

User = get_user_model()


@dataclass
class DataScanNewResultsData:
    scan_id: int
    scan_name: str
    new_results_count: int

    @classmethod
    def from_scan(cls, scan: DataScan, new_results_count: int):
        return cls(
            scan_id=scan.id,
            scan_name=scan.name,
            new_results_count=new_results_count,
        )


class DataScanNewResultsNotificationType(EmailNotificationTypeMixin, NotificationType):
    type = "data_scan_new_results"
    has_web_frontend_route = True

    def get_web_frontend_url(self, notification: Notification) -> str:
        base_url = settings.BASEROW_EMBEDDED_SHARE_URL
        query = urlencode(
            {
                "scan_id": notification.data.get("scan_id", ""),
                "scan_name": notification.data.get("scan_name", ""),
            }
        )
        return urljoin(base_url, f"/admin/data-scanner/results?{query}")

    @classmethod
    def notify_instance_admins(
        cls, scan: DataScan, new_results_count: int
    ) -> Optional[List[NotificationRecipient]]:
        """
        Sends a notification to all instance admins (staff users) informing
        them that new data scan results have been found.

        :param scan: The data scan that produced new results.
        :param new_results_count: The number of new results found in this run.
        :return: The list of created notification recipients, or None.
        """

        admins = User.objects.filter(is_staff=True, is_active=True)
        if not admins.exists():
            return None

        return NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=list(admins),
            data=asdict(DataScanNewResultsData.from_scan(scan, new_results_count)),
            sender=None,
            workspace=None,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context) -> str:
        count = notification.data.get("new_results_count", 0)
        scan_name = notification.data.get("scan_name", "")
        return ngettext(
            "%(count)d new result found for %(scan_name)s",
            "%(count)d new results found for %(scan_name)s",
            count,
        ) % {"count": count, "scan_name": scan_name}

    @classmethod
    def get_notification_description_for_email(
        cls, notification, context
    ) -> Optional[str]:
        count = notification.data.get("new_results_count", 0)
        scan_name = notification.data.get("scan_name", "")
        return ngettext(
            'The data scanner "%(scan_name)s" found %(count)d new match '
            "during its latest run. Review the results in the admin panel.",
            'The data scanner "%(scan_name)s" found %(count)d new matches '
            "during its latest run. Review the results in the admin panel.",
            count,
        ) % {"count": count, "scan_name": scan_name}
