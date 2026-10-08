from dataclasses import asdict, dataclass

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
    # Whether the usage and limit are those of the whole instance (a license based
    # limit) rather than of the workspace (a subscription quota), so that the
    # notification can say whose limit was reached.
    instance_wide: bool


class ApplicationUserLimitNotificationType(NotificationType):
    type = "application_user_limit"

    @classmethod
    def notify_admins_in_workspace(
        cls, workspace, threshold, usage, limit, instance_wide
    ):
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
            instance_wide=instance_wide,
        )
        return notify_admins_in_workspace(workspace, cls.type, asdict(data))

    @classmethod
    def get_notification_title(cls, notification):
        # An instance wide limit is reached by the instance as a whole, possibly
        # because of another workspace, so the wording says so instead of blaming
        # the notified workspace.
        instance_wide = notification.data.get("instance_wide", False)
        if notification.data["threshold"] >= 100:
            if instance_wide:
                return _("Application user limit of the instance reached")
            return _("Application user limit reached")
        numbers = {
            "usage": notification.data["usage"],
            "limit": notification.data["limit"],
        }
        if instance_wide:
            return (
                _("%(usage)s of %(limit)s application users of the instance used")
                % numbers
            )
        return _("%(usage)s of %(limit)s application users used") % numbers


def notify_application_user_threshold(
    workspace, usage, limit, threshold, instance_wide
):
    """
    Creates a single `application_user_limit` notification for the workspace admins,
    deduped per `(workspace, threshold)`.

    :param workspace: The workspace that reached the threshold.
    :param usage: The current application user usage.
    :param limit: The current application user limit.
    :param threshold: The threshold reached (e.g. 80 or 100).
    :param instance_wide: Whether the usage and limit are the instance's rather than
        the workspace's.
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
            instance_wide=instance_wide,
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
