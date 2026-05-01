from django.contrib.auth import get_user_model
from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from baserow.contrib.whiteboard.comments.exceptions import (
    InvalidWhiteboardCommentMessage,
    WhiteboardCommentDoesNotExist,
    WhiteboardCommentNotAuthor,
    WhiteboardCommentParentMismatch,
)
from baserow.contrib.whiteboard.comments.models import WhiteboardComment
from baserow.contrib.whiteboard.comments.operations import (
    CreateWhiteboardCommentOperationType,
    DeleteWhiteboardCommentOperationType,
    ListWhiteboardCommentsOperationType,
    ResolveWhiteboardCommentOperationType,
    UpdateWhiteboardCommentOperationType,
)
from baserow.contrib.whiteboard.comments.signals import (
    whiteboard_comment_created,
    whiteboard_comment_deleted,
    whiteboard_comment_resolved,
    whiteboard_comment_updated,
)
from baserow.contrib.whiteboard.handler import WhiteboardHandler
from baserow.core.handler import CoreHandler
from baserow.core.prosemirror.utils import (
    extract_mentioned_users_in_workspace,
    is_valid_prosemirror_document,
)

User = get_user_model()


def _safe_is_valid_prosemirror(message) -> bool:
    """`is_valid_prosemirror_document` only catches `ValueError` from
    prosemirror's parser, but malformed input (missing `type` key, wrong
    value types, …) can raise `KeyError`/`TypeError`. Treat any
    exception as "invalid" so the handler raises a clean
    `InvalidWhiteboardCommentMessage` instead of a 500."""

    try:
        return is_valid_prosemirror_document(message)
    except Exception:
        return False


class WhiteboardCommentHandler:
    def get_comment(
        self, comment_id: int, base_queryset: QuerySet | None = None
    ) -> WhiteboardComment:
        if base_queryset is None:
            base_queryset = WhiteboardComment.objects.all()
        try:
            return (
                base_queryset.select_related(
                    "whiteboard", "whiteboard__workspace", "user"
                )
                .prefetch_related("mentions")
                .get(id=comment_id)
            )
        except WhiteboardComment.DoesNotExist:
            raise WhiteboardCommentDoesNotExist

    def list_comments(self, user, whiteboard_id: int) -> list[WhiteboardComment]:
        whiteboard = WhiteboardHandler().get_whiteboard(whiteboard_id)
        CoreHandler().check_permissions(
            user,
            ListWhiteboardCommentsOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )
        replies_qs = (
            WhiteboardComment.objects.filter(parent_comment__isnull=False)
            .select_related("user")
            .prefetch_related("mentions")
            .order_by("created_on")
        )
        top_level = (
            WhiteboardComment.objects.filter(
                whiteboard_id=whiteboard_id, parent_comment__isnull=True
            )
            .select_related("user", "resolved_by")
            .prefetch_related("mentions", Prefetch("replies", queryset=replies_qs))
            .order_by("created_on")
        )
        out: list[WhiteboardComment] = []
        for top in top_level:
            out.append(top)
            for reply in top.replies.all():
                out.append(reply)
        return out

    def create_comment(
        self,
        user,
        whiteboard_id: int,
        message: dict,
        x: float | None = None,
        y: float | None = None,
        parent_comment_id: int | None = None,
    ) -> WhiteboardComment:
        whiteboard = WhiteboardHandler().get_whiteboard(whiteboard_id)
        CoreHandler().check_permissions(
            user,
            CreateWhiteboardCommentOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )
        if not _safe_is_valid_prosemirror(message):
            raise InvalidWhiteboardCommentMessage

        parent_comment = None
        if parent_comment_id is not None:
            parent_comment = self.get_comment(parent_comment_id)
            if parent_comment.whiteboard_id != whiteboard.id:
                raise WhiteboardCommentParentMismatch
            if parent_comment.parent_comment_id is not None:
                # Replies-of-replies are not supported; force depth 1.
                raise WhiteboardCommentParentMismatch
            # Replies inherit the thread anchor; ignore any incoming x/y.
            x = None
            y = None

        mentions = list(
            extract_mentioned_users_in_workspace(message, whiteboard.workspace)
        )
        comment = WhiteboardComment.objects.create(
            whiteboard=whiteboard,
            user=user,
            message=message,
            parent_comment=parent_comment,
            x=x,
            y=y,
        )
        if mentions:
            comment.mentions.set(mentions)

        whiteboard_comment_created.send(
            sender=self.__class__,
            comment=comment,
            whiteboard=whiteboard,
            user=user,
            mentions=mentions,
        )
        return comment

    def update_comment(self, user, comment: WhiteboardComment, message: dict):
        whiteboard = comment.whiteboard
        CoreHandler().check_permissions(
            user,
            UpdateWhiteboardCommentOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )
        if comment.user_id != user.id:
            raise WhiteboardCommentNotAuthor
        if not _safe_is_valid_prosemirror(message):
            raise InvalidWhiteboardCommentMessage

        old_mention_ids = set(comment.mentions.values_list("id", flat=True))
        new_mentions = list(
            extract_mentioned_users_in_workspace(message, whiteboard.workspace)
        )

        comment.message = message
        comment.save()
        comment.mentions.set(new_mentions)

        delta_mentions = [m for m in new_mentions if m.id not in old_mention_ids]
        whiteboard_comment_updated.send(
            sender=self.__class__,
            comment=comment,
            whiteboard=whiteboard,
            user=user,
            new_mentions=delta_mentions,
        )
        return comment

    def delete_comment(self, user, comment: WhiteboardComment):
        whiteboard = comment.whiteboard
        CoreHandler().check_permissions(
            user,
            DeleteWhiteboardCommentOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )
        if comment.user_id != user.id:
            raise WhiteboardCommentNotAuthor

        comment_id = comment.id
        parent_comment_id = comment.parent_comment_id
        comment.delete()

        whiteboard_comment_deleted.send(
            sender=self.__class__,
            comment_id=comment_id,
            parent_comment_id=parent_comment_id,
            whiteboard=whiteboard,
            user=user,
        )

    def resolve_comment(
        self, user, comment: WhiteboardComment, resolved: bool
    ) -> WhiteboardComment:
        whiteboard = comment.whiteboard
        CoreHandler().check_permissions(
            user,
            ResolveWhiteboardCommentOperationType.type,
            workspace=whiteboard.workspace,
            context=whiteboard,
        )
        if comment.parent_comment_id is not None:
            # Resolve only applies to threads (top-level comments).
            raise WhiteboardCommentParentMismatch

        comment.resolved = resolved
        comment.resolved_by = user if resolved else None
        comment.resolved_at = timezone.now() if resolved else None
        comment.save(update_fields=["resolved", "resolved_by", "resolved_at"])

        whiteboard_comment_resolved.send(
            sender=self.__class__,
            comment=comment,
            whiteboard=whiteboard,
            user=user,
            resolved=resolved,
        )
        return comment
