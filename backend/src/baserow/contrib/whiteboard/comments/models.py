from django.contrib.auth import get_user_model
from django.db import models

from baserow.contrib.whiteboard.models import Whiteboard
from baserow.core.mixins import CreatedAndUpdatedOnMixin

User = get_user_model()


class WhiteboardComment(CreatedAndUpdatedOnMixin, models.Model):
    """
    A user-authored comment pinned on a whiteboard. Top-level comments carry
    `(x, y)` scene coordinates; replies live under a `parent_comment` and
    inherit the thread's location. `resolved` only applies to top-level rows.
    """

    whiteboard = models.ForeignKey(
        Whiteboard,
        on_delete=models.CASCADE,
        related_name="comments",
        help_text="The whiteboard this comment belongs to.",
    )
    parent_comment = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        help_text=(
            "The thread root comment this comment replies to. "
            "Null on top-level comments."
        ),
    )
    user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="whiteboard_comments",
        help_text="The user who authored the comment.",
    )
    message = models.JSONField(
        default=dict, help_text="The rich text comment content (ProseMirror doc)."
    )
    mentions = models.ManyToManyField(
        User,
        related_name="whiteboard_comment_mentions",
        blank=True,
    )
    x = models.FloatField(
        null=True,
        blank=True,
        help_text="Scene X coordinate of the pin (top-level comments only).",
    )
    y = models.FloatField(
        null=True,
        blank=True,
        help_text="Scene Y coordinate of the pin (top-level comments only).",
    )
    resolved = models.BooleanField(
        default=False,
        help_text="Top-level comments only: whether the thread is resolved.",
    )
    resolved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_whiteboard_comments",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_on",)
        indexes = [
            models.Index(fields=["whiteboard", "parent_comment", "created_on"]),
        ]

    @property
    def is_reply(self) -> bool:
        return self.parent_comment_id is not None

    def get_parent(self):
        return self.whiteboard
