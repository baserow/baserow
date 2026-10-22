from rest_framework import serializers

from baserow.core.chat_runs.buffer import parse_cursor


class ChatRunSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    run_type = serializers.CharField()
    chat_id = serializers.IntegerField()
    status = serializers.CharField()
    error_code = serializers.CharField(allow_blank=True)
    cancel_requested_at = serializers.DateTimeField(allow_null=True)
    message = serializers.JSONField(allow_null=True)


class ChatRunCancelSerializer(serializers.Serializer):
    status = serializers.CharField()


class ChatRunStreamQuerySerializer(serializers.Serializer):
    cursor = serializers.CharField(
        required=False,
        help_text="The cursor of the last record received, to resume after it.",
    )

    def validate_cursor(self, value: str) -> str:
        try:
            parse_cursor(value)
        except ValueError:
            raise serializers.ValidationError("Invalid cursor.") from None
        return value
