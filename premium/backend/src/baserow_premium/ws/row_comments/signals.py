from django.db import transaction
from django.dispatch import receiver

from baserow.ws.registries import page_registry
from baserow.ws.tasks import broadcast_to_users
from baserow_premium.api.row_comments.serializers import RowCommentSerializer
from baserow_premium.row_comments import signals as row_comment_signals


@receiver(row_comment_signals.row_comment_created)
def row_comment_created(sender, row_comment, row, user, **kwargs):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            {
                "type": "row_comment_created",
                "row_comment": RowCommentSerializer(row_comment).data,
            },
            getattr(user, "web_socket_id", None),
            table_id=row_comment.table.id,
        )
    )


@receiver(row_comment_signals.row_comment_updated)
def row_comment_updated(sender, row_comment, row, user, **kwargs):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            {
                "type": "row_comment_updated",
                "row_comment": RowCommentSerializer(row_comment).data,
            },
            getattr(user, "web_socket_id", None),
            table_id=row_comment.table.id,
        )
    )


@receiver(row_comment_signals.row_comment_deleted)
def row_comment_deleted(sender, row_comment, user, **kwargs):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            {
                "type": "row_comment_deleted",
                "row_comment": RowCommentSerializer(row_comment).data,
            },
            getattr(user, "web_socket_id", None),
            table_id=row_comment.table.id,
        )
    )


@receiver(row_comment_signals.row_comment_restored)
def row_comment_restored(sender, row_comment, user, **kwargs):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            {
                "type": "row_comment_restored",
                "row_comment": RowCommentSerializer(row_comment).data,
            },
            getattr(user, "web_socket_id", None),
            table_id=row_comment.table.id,
        )
    )


@receiver(row_comment_signals.row_comments_notification_mode_updated)
def row_comments_notification_mode_updated(
    sender, user, table, row_id, mode, include_user_in_signal, **kwargs
):
    ignore_web_socket_it = (
        None if include_user_in_signal else getattr(user, "web_socket_id", None)
    )
    payload = {
        "type": "row_comments_notification_mode_updated",
        "table_id": table.id,
        "row_id": row_id,
        "mode": mode,
    }
    transaction.on_commit(
        lambda: broadcast_to_users.delay([user.id], payload, ignore_web_socket_it)
    )
