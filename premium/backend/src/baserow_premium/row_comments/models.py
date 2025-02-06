from enum import Enum

from django.contrib.auth import get_user_model
from django.db import models

from baserow.contrib.database.table.models import Table
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    TrashableModelMixin,
)

User = get_user_model()


class RowComment(
    CreatedAndUpdatedOnMixin, HierarchicalModelMixin, TrashableModelMixin, models.Model
):
    """
    A user made comment on a specific row in a user table in Baserow.
    """

    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        help_text="The table the row this comment is for is found in. ",
    )
    row_id = models.PositiveIntegerField(
        help_text="The id of the row the comment is for."
    )
    user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        help_text="The user who made the comment.",
    )
    comment = models.TextField(
        help_text="The users comment.", null=True, editable=False
    )  # Deprecated, will be removed in a future release.
    message = models.JSONField(default=dict, help_text="The rich text comment content.")
    mentions = models.ManyToManyField(User, related_name="row_comment_mentions")

    class Meta:
        db_table = "database_rowcomment"
        ordering = ("-created_on",)
        indexes = [models.Index(fields=["table", "row_id", "-created_on"])]

    def get_parent(self):
        table_model = self.table.get_model()
        return table_model.objects.get(id=self.row_id)


class RowCommentsNotificationModes(str, Enum):
    # Use this mode to subscribe to all comments on a table.
    MODE_ALL_COMMENTS = "all"

    # Use this mode to subscribe to only mentions on a table row.
    MODE_ONLY_MENTIONS = "mentions"


ALL_ROW_COMMENT_NOTIFICATION_MODES = [
    getattr(mode, "value") for mode in RowCommentsNotificationModes
]


ROW_COMMENT_NOTIFICATION_DEFAULT_MODE = RowCommentsNotificationModes.MODE_ONLY_MENTIONS


class RowCommentsNotificationMode(CreatedAndUpdatedOnMixin, models.Model):
    """
    A many to many relationship between users and table rows to keep track of
    how users want to be notified about new comments on rows. The default mode
    is to not be notified only when the user is mentioned in a comment.
    If the entry is missing for a user and row, the default mode is used.
    """

    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        help_text="The table where the row is found in.",
    )
    row_id = models.PositiveIntegerField(
        help_text="The id of the row the subscription is for."
    )
    user = models.ForeignKey(
        User,
        null=True,
        on_delete=models.CASCADE,
        help_text="The user who wants to receive notifications for this row.",
    )
    mode = models.CharField(
        max_length=32,
        choices=(
            (RowCommentsNotificationModes.MODE_ALL_COMMENTS, "All comments"),
            (RowCommentsNotificationModes.MODE_ONLY_MENTIONS, "Only mentions"),
        ),
        default=ROW_COMMENT_NOTIFICATION_DEFAULT_MODE,
        help_text="The notification mode for this user and row.",
    )

    class Meta:
        unique_together = ("table", "row_id", "user")
