from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.whiteboard.api.comments.serializers import (
    WhiteboardCommentSerializer,
)
from baserow.contrib.whiteboard.comments.signals import (
    whiteboard_comment_created,
    whiteboard_comment_deleted,
    whiteboard_comment_resolved,
    whiteboard_comment_updated,
)
from baserow.ws.registries import page_registry


def _broadcast(payload, whiteboard_id, user):
    page_type = page_registry.get("whiteboard")
    page_type.broadcast(
        payload,
        whiteboard_id=whiteboard_id,
        ignore_web_socket_id=getattr(user, "web_socket_id", None),
    )


@receiver(whiteboard_comment_created)
def _on_created(sender, comment, whiteboard, user, **kwargs):
    serialized = WhiteboardCommentSerializer(comment).data
    transaction.on_commit(
        lambda: _broadcast(
            {
                "type": "whiteboard_comment_created",
                "whiteboard_id": whiteboard.id,
                "comment": serialized,
            },
            whiteboard.id,
            user,
        )
    )


@receiver(whiteboard_comment_updated)
def _on_updated(sender, comment, whiteboard, user, **kwargs):
    serialized = WhiteboardCommentSerializer(comment).data
    transaction.on_commit(
        lambda: _broadcast(
            {
                "type": "whiteboard_comment_updated",
                "whiteboard_id": whiteboard.id,
                "comment": serialized,
            },
            whiteboard.id,
            user,
        )
    )


@receiver(whiteboard_comment_deleted)
def _on_deleted(sender, comment_id, parent_comment_id, whiteboard, user, **kwargs):
    transaction.on_commit(
        lambda: _broadcast(
            {
                "type": "whiteboard_comment_deleted",
                "whiteboard_id": whiteboard.id,
                "comment_id": comment_id,
                "parent_comment_id": parent_comment_id,
            },
            whiteboard.id,
            user,
        )
    )


@receiver(whiteboard_comment_resolved)
def _on_resolved(sender, comment, whiteboard, user, resolved, **kwargs):
    serialized = WhiteboardCommentSerializer(comment).data
    transaction.on_commit(
        lambda: _broadcast(
            {
                "type": "whiteboard_comment_resolved",
                "whiteboard_id": whiteboard.id,
                "comment": serialized,
                "resolved": resolved,
            },
            whiteboard.id,
            user,
        )
    )
