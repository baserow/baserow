from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from baserow.core.prosemirror.utils import is_valid_prosemirror_document
from baserow_premium.row_comments.models import (
    ALL_ROW_COMMENT_NOTIFICATION_MODES,
    RowComment,
)


@extend_schema_serializer(deprecate_fields=["comment"])
class RowCommentMentionableSerializer(serializers.Serializer):
    type = serializers.CharField(
        help_text="The mention target type, stored as the mention's `kind`."
    )
    id = serializers.IntegerField(help_text="The id to mention.")
    name = serializers.CharField(help_text="The label shown for the mention.")


class RowCommentSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField(
        help_text="The author's name: the user's first name, or the agent "
        "application's name when an agent posted the comment."
    )
    author_application_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
        help_text="Set when an agent application posted the comment.",
    )
    edited = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_first_name(self, instance):
        if instance.user_id is not None:
            return instance.user.first_name
        if instance.author_application_id is not None:
            return instance.author_application.name
        return None

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
            "author_application_id",
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


class RowCommentViewQueryParamsSerializer(serializers.Serializer):
    view = serializers.IntegerField(required=False)


class RowCommentsNotificationModeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(
        choices=ALL_ROW_COMMENT_NOTIFICATION_MODES,
        help_text="The mode to use to receive notifications for new comments on a table row.",
    )
