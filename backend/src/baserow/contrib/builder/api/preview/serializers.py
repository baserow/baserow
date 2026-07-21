from rest_framework import serializers


class BuilderPreviewGrantRequestSerializer(serializers.Serializer):
    path = serializers.CharField(required=False, allow_blank=True, default="/")


class BuilderPreviewGrantResponseSerializer(serializers.Serializer):
    url = serializers.URLField()


class BuilderPreviewHandoffRequestSerializer(serializers.Serializer):
    preview_handoff = serializers.CharField()


class BuilderPreviewHandoffResponseSerializer(serializers.Serializer):
    preview_session = serializers.CharField()
    expires_in = serializers.IntegerField(min_value=1)
