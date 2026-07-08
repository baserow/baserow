from rest_framework import serializers


class BuilderPreviewGrantRequestSerializer(serializers.Serializer):
    path = serializers.CharField(required=False, allow_blank=True, default="/")


class BuilderPreviewGrantResponseSerializer(serializers.Serializer):
    url = serializers.URLField()
