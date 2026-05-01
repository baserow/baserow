from dataclasses import asdict, dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.dispatch import receiver
from django.utils.translation import gettext as _

from baserow.contrib.whiteboard.comments.signals import (
    whiteboard_comment_created,
    whiteboard_comment_updated,
)
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.registries import (
    EmailNotificationTypeMixin,
    NotificationType,
)
from baserow.core.prosemirror.utils import prosemirror_doc_to_plain_text

User = get_user_model()


@dataclass
class WhiteboardCommentNotificationData:
    workspace_id: int
    workspace_name: str
    whiteboard_id: int
    whiteboard_name: str
    comment_id: int
    parent_comment_id: int | None
    message: dict

    @classmethod
    def from_comment(cls, comment):
        whiteboard = comment.whiteboard
        workspace = whiteboard.workspace
        return cls(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            whiteboard_id=whiteboard.id,
            whiteboard_name=whiteboard.name,
            comment_id=comment.id,
            parent_comment_id=comment.parent_comment_id,
            message=comment.message,
        )


class WhiteboardCommentMentionNotificationType(
    EmailNotificationTypeMixin, NotificationType
):
    type = "whiteboard_comment_mention"
    has_web_frontend_route = True

    @classmethod
    def notify_mentioned_users(cls, comment, mentioned_users):
        if not mentioned_users:
            return
        NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=list(mentioned_users),
            data=asdict(WhiteboardCommentNotificationData.from_comment(comment)),
            sender=comment.user,
            workspace=comment.whiteboard.workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _(
            "%(user)s mentioned you in a whiteboard comment on %(whiteboard_name)s."
        ) % {
            "user": notification.sender.first_name,
            "whiteboard_name": notification.data["whiteboard_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return prosemirror_doc_to_plain_text(notification.data["message"])


class WhiteboardCommentReplyNotificationType(
    EmailNotificationTypeMixin, NotificationType
):
    type = "whiteboard_comment_reply"
    has_web_frontend_route = True

    @classmethod
    def notify_thread_participants(cls, reply, exclude_user_ids):
        thread = reply.parent_comment
        if thread is None:
            return
        # Anyone who: authored the thread root, OR has been mentioned in
        # the thread root, OR has been mentioned in any reply under the
        # thread. Minus the exclude set (reply author + just-mentioned).
        participants = (
            User.objects.filter(
                Q(id=thread.user_id)
                | Q(whiteboard_comment_mentions=thread)
                | Q(whiteboard_comment_mentions__parent_comment=thread)
            )
            .exclude(id__in=exclude_user_ids)
            .exclude(profile__to_be_deleted=True)
            .distinct()
        )
        recipients = list(participants)
        if not recipients:
            return
        NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=recipients,
            data=asdict(WhiteboardCommentNotificationData.from_comment(reply)),
            sender=reply.user,
            workspace=reply.whiteboard.workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _(
            "%(user)s replied to a whiteboard comment thread on %(whiteboard_name)s."
        ) % {
            "user": notification.sender.first_name,
            "whiteboard_name": notification.data["whiteboard_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        return prosemirror_doc_to_plain_text(notification.data["message"])


@receiver(whiteboard_comment_created)
def _notify_on_create(sender, comment, mentions, **kwargs):
    """
    On a new comment:
      - mentioned users → mention notification
      - if it's a reply: thread participants (parent author + previously
        mentioned anywhere in the thread) → reply notification, but only
        if they didn't already receive the mention notification for this
        same event.
    """

    mentioned_ids = {u.id for u in (mentions or [])}

    def _do():
        if mentioned_ids:
            WhiteboardCommentMentionNotificationType.notify_mentioned_users(
                comment, mentions
            )
        if comment.parent_comment_id is not None:
            exclude = {comment.user_id, *mentioned_ids}
            WhiteboardCommentReplyNotificationType.notify_thread_participants(
                comment, exclude
            )

    transaction.on_commit(_do)


@receiver(whiteboard_comment_updated)
def _notify_on_update(sender, comment, new_mentions, **kwargs):
    """Only newly-mentioned users get a notification on edit."""

    if not new_mentions:
        return
    transaction.on_commit(
        lambda: WhiteboardCommentMentionNotificationType.notify_mentioned_users(
            comment, new_mentions
        )
    )
