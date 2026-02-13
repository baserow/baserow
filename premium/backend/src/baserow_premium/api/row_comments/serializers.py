from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from baserow.core.prosemirror.utils import is_valid_prosemirror_document
from baserow_premium.row_comments.models import (
    ALL_ROW_COMMENT_NOTIFICATION_MODES,
    RowComment,
)


@extend_schema_serializer(deprecate_fields=["comment"])
class RowCommentSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(
        max_length=32, source="user.first_name", required=False
    )
    edited = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    def get_edited(self, instance):
        return instance.updated_on > instance.created_on

    def get_message(self, instance):
        # Ensure the comment content is not returned if it has been trashed
        if instance.trashed:
            return None
        return instance.message

    class Meta:
        model = RowComment
        fields = (
            "id",
            "user_id",
            "first_name",
            "table_id",
            "row_id",
            "message",
            "created_on",
            "updated_on",
            "edited",
            "trashed",
        )


@extend_schema_serializer(deprecate_fields=["comment"])
class RowCommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RowComment
        fields = ("message",)
        extra_kwargs = {
            "message": {"required": True},
        }

    def validate_message(self, value):
        if not is_valid_prosemirror_document(value):
            raise serializers.ValidationError(
                "The message must be a valid ProseMirror JSON document."
            )
        return value


class RowCommentsNotificationModeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(
        choices=ALL_ROW_COMMENT_NOTIFICATION_MODES,
        help_text="The mode to use to receive notifications for new comments on a table row.",
    )
