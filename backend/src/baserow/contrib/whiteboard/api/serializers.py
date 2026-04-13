from rest_framework import serializers


class WhiteboardContentSerializer(serializers.Serializer):
    content = serializers.JSONField(required=True)


class BroadcastChangesSerializer(serializers.Serializer):
    changes = serializers.JSONField(required=True)
