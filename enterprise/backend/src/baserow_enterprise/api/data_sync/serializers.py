from rest_framework import serializers

from baserow_enterprise.data_sync.models import PeriodicDataSyncInterval


class PeriodicDataSyncIntervalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodicDataSyncInterval
        fields = (
            "interval",
            "when",
            "automatically_deactivated",
        )

    def validate_automatically_deactivated(self, value):
        if value is True:
            raise serializers.ValidationError(
                "automatically_deactivated can only be set to False."
            )
        return value
