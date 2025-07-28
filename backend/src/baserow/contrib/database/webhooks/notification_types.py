from dataclasses import asdict, dataclass
from typing import List

from django.conf import settings
from django.utils.translation import gettext as _

from baserow.core.notifications.helpers import notify_admins_in_workspace
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
    ) -> List[NotificationRecipient]:
        """
        Creates a notification of this type for each admin in the workspace that the
        webhook belongs to.

        :param webhook: The webhook that was deactivated.
        :return: A list of notification recipients that have been created.
        """

        workspace = webhook.table.database.workspace
        return notify_admins_in_workspace(
            workspace, cls.type, asdict(DeactivatedWebhookData.from_webhook(webhook))
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


@dataclass
class WebhookPayloadTooLargeData:
    webhook_id: int
    table_id: int
    database_id: int
    webhook_name: str
    event_id: str
    batch_limit: int

    @classmethod
    def from_webhook(cls, webhook: TableWebhook, event_id: str):
        return cls(
            webhook_id=webhook.id,
            table_id=webhook.table_id,
            database_id=webhook.table.database_id,
            webhook_name=webhook.name,
            event_id=event_id,
            batch_limit=webhook.batch_limit,
        )


class WebhookPayloadTooLargeNotificationType(
    EmailNotificationTypeMixin, NotificationType
):
    type = "webhook_payload_too_large"
    has_web_frontend_route = True

    @classmethod
    def notify_admins_in_workspace(
        cls, webhook: TableWebhook, event_id: str
    ) -> List[NotificationRecipient]:
        """
        Creates a notification of this type for each admin in the workspace that the
        webhook belongs to.

        :param webhook: The webhook trying to send a payload that is too large.
        :param event_id: The event id that triggered the notification.
        :return: A list of notification recipients that have been created.
        """

        workspace = webhook.table.database.workspace
        return notify_admins_in_workspace(
            workspace,
            cls.type,
            asdict(WebhookPayloadTooLargeData.from_webhook(webhook, event_id)),
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _("%(name)s webhook payload too large.") % {
            "name": notification.data["webhook_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return _(
            "The payload for the %(name)s webhook with event ID %(event_id)s "
            "was too large. The content has been split into multiple batches, but "
            "data above the batch limit of %(batch_limit)s was discarded."
        ) % {
            "name": notification.data["webhook_name"],
            "event_id": notification.data["event_id"],
            "batch_limit": notification.data["batch_limit"],
        }
