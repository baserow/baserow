from rest_framework import serializers


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
