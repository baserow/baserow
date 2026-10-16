from rest_framework import serializers


class UpdatePremiumDashboardAttributesSerializer(serializers.Serializer):
    show_logo = serializers.BooleanField(required=False)
