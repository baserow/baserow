from dataclasses import asdict, dataclass

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext as _

from baserow.core.notifications.helpers import notify_admins_in_workspace
from baserow.core.notifications.models import Notification
from baserow.core.notifications.registries import NotificationType


@dataclass
class ApplicationUserLimitNotificationData:
    workspace_id: int
    workspace_name: str
    # `threshold` (e.g. 80 / 100) is the dedup key per workspace.
    threshold: int
    usage: int
    limit: int
    # Whether the limit is enforced (hard limit) so the frontend can pick the right
    # wording for the 100% notification.
    enforced: bool


class ApplicationUserLimitNotificationType(NotificationType):
    type = "application_user_limit"

    @classmethod
    def notify_admins_in_workspace(cls, workspace, threshold, usage, limit):
        """
        Creates a notification of this type for each admin in the workspace. Only
        admins are notified because they are the ones who can act on the limit,
        e.g. by upgrading the license or subscription.
        """

        data = ApplicationUserLimitNotificationData(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            threshold=threshold,
            usage=usage,
            limit=limit,
            enforced=settings.BASEROW_APPLICATION_USER_LIMIT_ENFORCED,
        )
        return notify_admins_in_workspace(workspace, cls.type, asdict(data))

    @classmethod
    def get_notification_title(cls, notification):
        if notification.data["threshold"] >= 100:
            return _("Application user limit reached")
        return _("You've used %(threshold)s%% of your application user limit") % {
            "threshold": notification.data["threshold"]
        }


def notify_application_user_threshold(workspace, usage, limit, threshold):
    """
    Creates a single `application_user_limit` notification for the workspace admins,
    deduped per `(workspace, threshold)`.

    :param workspace: The workspace that reached the threshold.
    :param usage: The current application user usage.
    :param limit: The current application user limit.
    :param threshold: The threshold reached (e.g. 80 or 100).
    """

    def _check_and_create():
        already_sent = Notification.objects.filter(
            type=ApplicationUserLimitNotificationType.type,
            workspace=workspace,
            data__contains={"threshold": threshold},
        ).exists()
        if already_sent:
            return

        ApplicationUserLimitNotificationType.notify_admins_in_workspace(
            workspace=workspace,
            threshold=threshold,
            usage=usage,
            limit=limit,
        )

    # The check + create runs together at commit time via `transaction.on_commit`, so
    # that the dedup query sees committed state and that the notification survives the
    # rollback of the transaction that raised the application user limit exception.
    transaction.on_commit(_check_and_create)


def clear_application_user_threshold(workspace, threshold):
    """
    Removes any outstanding `application_user_limit` notification for the given
    `(workspace, threshold)`. Called when usage drops back below the threshold so that
    crossing it again later notifies anew instead of being deduped away.

    :param workspace: The workspace to clear the notification for.
    :param threshold: The threshold to clear (e.g. 80 or 100).
    """

    Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type,
        workspace=workspace,
        data__contains={"threshold": threshold},
    ).delete()
