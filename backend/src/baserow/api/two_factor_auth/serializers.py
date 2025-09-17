from rest_framework import serializers


class TwoFactorAuthSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(read_only=True)
