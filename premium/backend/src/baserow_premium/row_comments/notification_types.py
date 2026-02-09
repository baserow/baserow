from dataclasses import asdict, dataclass
from typing import List, Optional

from django.dispatch import receiver
from django.utils.translation import gettext as _

from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.notifications.registries import (
    EmailNotificationTypeMixin,
    NotificationType,
)
from baserow.core.prosemirror.utils import prosemirror_doc_to_plain_text
from baserow_premium.row_comments.handler import RowCommentHandler
from baserow_premium.row_comments.models import (
    RowCommentsNotificationMode,
    RowCommentsNotificationModes,
)

from .signals import row_comment_created, row_comment_updated


@dataclass
class RowCommentNotificationData:
    database_id: int
    database_name: str
    table_id: int
    table_name: str
    row_id: int
    row_name: str
    comment_id: int
    message: str

    @classmethod
    def from_row_comment(cls, row_comment, row):
        return cls(
            database_id=row_comment.table.database.id,
            database_name=row_comment.table.database.name,
            table_id=row_comment.table_id,
            table_name=row_comment.table.name,
            row_id=int(row_comment.row_id),
            row_name=str(row),
            comment_id=row_comment.id,
            message=row_comment.message,
        )


class RowCommentMentionNotificationType(EmailNotificationTypeMixin, NotificationType):
    type = "row_comment_mention"
    has_web_frontend_route = True

    @classmethod
    def notify_mentioned_users(cls, row_comment, row, mentions):
        """
        Creates a notification for each user that is mentioned in the comment.

        :param row_comment: The comment that was created.
        :param mentions: The list of users that are mentioned.
        :return: The list of created notifications.
        """

        notification_data = RowCommentNotificationData.from_row_comment(
            row_comment, row
        )
        NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=mentions,
            data=asdict(notification_data),
            sender=row_comment.user,
            workspace=row_comment.table.database.workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _("%(user)s mentioned you in row %(row_name)s in %(table_name)s.") % {
            "user": notification.sender.first_name,
            "row_name": notification.data.get("row_name", notification.data["row_id"]),
            "table_name": notification.data["table_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return prosemirror_doc_to_plain_text(notification.data["message"])


class RowCommentNotificationType(EmailNotificationTypeMixin, NotificationType):
    """
    This notification type is used to notify users that are subscribed to
    receive new comments on a given row. This notification will only be sent if
    the user is not the sender of the comment or if they have been mentioned, as
    they will already receive the `RowCommentMentionNotificationType`
    notification for that.
    """

    type = "row_comment"
    has_web_frontend_route = True

    @classmethod
    def notify_subscribed_users(
        cls, row_comment, row, users_to_notify
    ) -> Optional[List[NotificationRecipient]]:
        """
        Creates a notification for each user that is subscribed to receive comments on
        the row on which the comment was created.

        :param row_comment: The comment that was created.
        :param users_to_notify: The list of users that are subscribed to receive
            comments on the row.
        :return: The list of created notifications.
        """

        if not users_to_notify:
            return

        notification_data = RowCommentNotificationData.from_row_comment(
            row_comment, row
        )
        return NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=users_to_notify,
            data=asdict(notification_data),
            sender=row_comment.user,
            workspace=row_comment.table.database.workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _("%(user)s posted a comment in row %(row_name)s in %(table_name)s.") % {
            "user": notification.sender.first_name,
            "row_name": notification.data.get("row_name", notification.data["row_id"]),
            "table_name": notification.data["table_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return prosemirror_doc_to_plain_text(notification.data["message"])


@receiver(row_comment_created)
def on_row_comment_created(sender, row_comment, row, user, mentions, **kwargs):
    if mentions:
        RowCommentMentionNotificationType.notify_mentioned_users(
            row_comment, row, mentions
        )

    user_ids_to_exclude = [mention.id for mention in mentions]
    users_to_notify = RowCommentHandler.get_users_to_notify_for_comment(
        row_comment, user_ids_to_exclude
    )
    if users_to_notify:
        RowCommentNotificationType.notify_subscribed_users(
            row_comment, row, users_to_notify
        )

    # The sender will probably wants to receive the notification about all
    # future comments posted on this row if this is the first comment, so change
    # the notification mode if they have not already changed it.

    table_id = row_comment.table_id
    row_id = row_comment.row_id
    if not RowCommentsNotificationMode.objects.filter(
        user=user, table_id=table_id, row_id=row_id
    ).exists():
        RowCommentHandler.update_row_comments_notification_mode(
            user,
            table_id,
            row_id,
            RowCommentsNotificationModes.MODE_ALL_COMMENTS.value,
            include_user_in_signal=True,
        )


@receiver(row_comment_updated)
def on_row_comment_updated(sender, row_comment, row, user, mentions, **kwargs):
    if mentions:
        RowCommentMentionNotificationType.notify_mentioned_users(
            row_comment, row, mentions
        )
