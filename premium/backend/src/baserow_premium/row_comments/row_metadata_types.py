from typing import Any, Dict, List

from django.db.models import Count

from baserow_premium.row_comments.models import (
    ALL_ROW_COMMENT_NOTIFICATION_MODES,
    ROW_COMMENT_NOTIFICATION_DEFAULT_MODE,
    RowComment,
    RowCommentsNotificationMode,
)
from rest_framework import serializers
from rest_framework.fields import Field

from baserow.contrib.database.rows.registries import RowMetadataType


class RowCommentCountMetadataType(RowMetadataType):
    type = "row_comment_count"

    def generate_metadata_for_rows(
        self, user, table, row_ids: List[int]
    ) -> Dict[int, Any]:
        return {
            r["row_id"]: r["count"]
            for r in (
                RowComment.objects.filter(table=table, row_id__in=row_ids)
                .values("row_id")
                .order_by("row_id")
                .annotate(count=Count("row_id"))
            )
        }

    def get_example_serializer_field(self) -> Field:
        return serializers.IntegerField(
            min_value=0,
            help_text="How many row comments exist for this row.",
            required=False,
        )


class RowCommentsNotificationModeMetadataType(RowMetadataType):
    type = "row_comments_notification_mode"

    def generate_metadata_for_rows(
        self, user, table, row_ids: List[int]
    ) -> Dict[int, Any]:
        """
        Returns a dictionary keyed by row id with the value being the notification mode
        for the user and row.
        If no or an anonymous user is provided then an empty dict is returned.
        """

        if not user or not user.id:
            return {}

        return {
            row["row_id"]: row["mode"]
            for row in (
                RowCommentsNotificationMode.objects.filter(
                    user=user,
                    table=table,
                    row_id__in=row_ids,
                )
                .exclude(mode=ROW_COMMENT_NOTIFICATION_DEFAULT_MODE)
                .values("row_id", "mode")
            )
        }

    def get_example_serializer_field(self) -> Field:
        return serializers.ChoiceField(
            required=False, choices=ALL_ROW_COMMENT_NOTIFICATION_MODES
        )
