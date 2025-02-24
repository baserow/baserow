from dataclasses import asdict, dataclass
from typing import List, Optional

from django.conf import settings
from django.utils.translation import gettext as _

from baserow.core.models import WORKSPACE_USER_PERMISSION_ADMIN, WorkspaceUser
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.notifications.registries import (
    EmailNotificationTypeMixin,
    NotificationType,
)

from .models import TableWebhook


@dataclass
class DeactivatedWebhookData:
    webhook_id: int
    table_id: int
    database_id: int
    webhook_name: str

    @classmethod
    def from_webhook(cls, webhook):
        return cls(
            webhook_id=webhook.id,
            table_id=webhook.table_id,
            database_id=webhook.table.database_id,
            webhook_name=webhook.name,
        )


class WebhookDeactivatedNotificationType(EmailNotificationTypeMixin, NotificationType):
    type = "webhook_deactivated"
    has_web_frontend_route = True

    @classmethod
    def notify_admins_in_workspace(
        cls, webhook: TableWebhook
    ) -> Optional[List[NotificationRecipient]]:
        """
        Creates a notification for each user that is subscribed to receive comments on
        the row on which the comment was created.

        :param webhook: The comment that was created.
        :return:
        """

        workspace = webhook.table.database.workspace
        admins_workspace_users = WorkspaceUser.objects.filter(
            workspace=workspace,
            permissions=WORKSPACE_USER_PERMISSION_ADMIN,
            user__profile__to_be_deleted=False,
            user__is_active=True,
        ).select_related("user")
        admins_in_workspace = [admin.user for admin in admins_workspace_users]

        return NotificationHandler.create_direct_notification_for_users(
            notification_type=WebhookDeactivatedNotificationType.type,
            recipients=admins_in_workspace,
            data=asdict(DeactivatedWebhookData.from_webhook(webhook)),
            sender=None,
            workspace=webhook.table.database.workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _("%(name)s webhook has been deactivated.") % {
            "name": notification.data["webhook_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return _(
            "The webhook failed more than %(max_failures)s consecutive times and "
            "was therefore deactivated."
        ) % {
            "max_failures": settings.BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES,
        }
