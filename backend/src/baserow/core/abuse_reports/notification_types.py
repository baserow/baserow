from dataclasses import asdict, dataclass
from typing import List, Optional

from django.contrib.auth import get_user_model
from django.template.defaultfilters import truncatechars
from django.utils.translation import gettext as _

from baserow.core.emails import prevent_autolink
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.notifications.registries import (
    EmailNotificationTypeMixin,
    NotificationType,
)

from .models import AbuseReport

User = get_user_model()


@dataclass
class AbuseReportCreatedNotificationData:
    resource_type: str
    resource_id: int
    resource_name: str
    workspace_id: Optional[int]
    workspace_name: str
    public_url: str
    reporter_name: str
    reporter_email: str
    description: str

    @classmethod
    def from_report(cls, report: AbuseReport):
        return cls(
            resource_type=report.resource_type,
            resource_id=report.resource_id,
            resource_name=report.resource_name,
            workspace_id=report.workspace_id,
            workspace_name=report.workspace_name,
            public_url=report.public_url,
            reporter_name=report.reporter_name,
            reporter_email=report.reporter_email,
            description=report.description,
        )


class AbuseReportCreatedNotificationType(EmailNotificationTypeMixin, NotificationType):
    type = "abuse_report_created"
    # The summary email would turn the notification title into a link to this URL.
    # Because the reported page is specifically suspected of phishing, the email must
    # not link to it; the in-app notification renders it as an explicitly labeled
    # link instead.
    has_web_frontend_route = False

    @classmethod
    def notify_instance_admins(
        cls, report: AbuseReport
    ) -> Optional[List[NotificationRecipient]]:
        admins = User.objects.filter(is_staff=True, is_active=True)
        if not admins.exists():
            return None

        recipients = NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=list(admins),
            data=asdict(AbuseReportCreatedNotificationData.from_report(report)),
            sender=None,
            workspace=None,
        )

        report.admins_notified = True
        report.save(update_fields=["admins_notified"])

        return recipients

    @classmethod
    def get_notification_title_for_email(cls, notification, context) -> str:
        return _("%(resource_name)s has been reported for abuse") % {
            "resource_name": prevent_autolink(
                truncatechars(notification.data.get("resource_name", ""), 64)
            ),
        }

    @classmethod
    def get_notification_description_for_email(
        cls, notification, context
    ) -> Optional[str]:
        # The reported URL comes first so that it's always visible regardless of how
        # long the rest of the text is. The reporter values are untrusted user
        # input, so they're truncated, and everything is de-linkified so that the
        # suspected phishing page can't be opened with a single click from the
        # email.
        return _(
            "%(public_url)s — %(reporter_name)s (%(reporter_email)s) wrote: "
            "%(description)s"
        ) % {
            "public_url": prevent_autolink(notification.data.get("public_url", "")),
            "reporter_name": prevent_autolink(
                truncatechars(notification.data.get("reporter_name", ""), 64)
            ),
            "reporter_email": prevent_autolink(
                truncatechars(notification.data.get("reporter_email", ""), 64)
            ),
            "description": prevent_autolink(
                truncatechars(notification.data.get("description", ""), 200)
            ),
        }
