from typing import List

from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    Workspace,
    WorkspaceUser,
)
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient


def notify_admins_in_workspace(
    workspace: Workspace, notification_type: str, data: dict
) -> List[NotificationRecipient]:
    """
    Notifies all admins in the workspace about an important event, such as a webhook
    deactivation or a payload exceeding size limits.

    :param workspace: The workspace whose admins will be notified.
    :param notification_type: The type of notification to send.
    :param data: The data to include in the notification.
    :return: A list of created notification recipients.
    """

    admins_workspace_users = WorkspaceUser.objects.filter(
        workspace=workspace,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
        user__profile__to_be_deleted=False,
        user__is_active=True,
    ).select_related("user")
    admins_in_workspace = [admin.user for admin in admins_workspace_users]

    return NotificationHandler.create_direct_notification_for_users(
        notification_type=notification_type,
        recipients=admins_in_workspace,
        data=data,
        sender=None,
        workspace=workspace,
    )
