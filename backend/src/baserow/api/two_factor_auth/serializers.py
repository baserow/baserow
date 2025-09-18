from rest_framework import serializers


class TwoFactorAuthSerializer(serializers.Serializer):
    type = serializers.CharField()
    enabled = serializers.BooleanField(read_only=True)
