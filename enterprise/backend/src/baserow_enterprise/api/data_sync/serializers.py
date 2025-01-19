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
        extra_kwargs = {"automatically_deactivated": {"read_only": True}}
