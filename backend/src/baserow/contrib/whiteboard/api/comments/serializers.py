from rest_framework import serializers

from baserow.contrib.whiteboard.comments.models import WhiteboardComment
from baserow.core.prosemirror.utils import is_valid_prosemirror_document


def _validate_prosemirror(value):
    # `is_valid_prosemirror_document` only catches `ValueError` from the
    # underlying parser, but malformed input (e.g. missing `type` key)
    # can raise `KeyError`/`TypeError`. We treat any exception as
    # "invalid" so the API returns 400 instead of 500 on garbage input.
    try:
        valid = is_valid_prosemirror_document(value)
    except Exception:
        valid = False
    if not valid:
        raise serializers.ValidationError(
            "The message must be a valid ProseMirror JSON document."
        )
    return value


class WhiteboardCommentSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(
        max_length=165, source="user.first_name", required=False
    )
    edited = serializers.SerializerMethodField()

    def get_edited(self, instance):
        return instance.updated_on > instance.created_on

    class Meta:
        model = WhiteboardComment
        fields = (
            "id",
            "whiteboard_id",
            "parent_comment_id",
            "user_id",
            "first_name",
            "message",
            "x",
            "y",
            "resolved",
            "resolved_by_id",
            "resolved_at",
            "created_on",
            "updated_on",
            "edited",
        )


class CreateWhiteboardCommentSerializer(serializers.Serializer):
    message = serializers.JSONField(required=True)
    parent_comment_id = serializers.IntegerField(required=False, allow_null=True)
    x = serializers.FloatField(required=False, allow_null=True)
    y = serializers.FloatField(required=False, allow_null=True)

    def validate_message(self, value):
        return _validate_prosemirror(value)


class UpdateWhiteboardCommentSerializer(serializers.Serializer):
    message = serializers.JSONField(required=True)

    def validate_message(self, value):
        return _validate_prosemirror(value)


class ResolveWhiteboardCommentSerializer(serializers.Serializer):
    resolved = serializers.BooleanField(required=True)
