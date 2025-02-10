from rest_framework import serializers

from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
)


class LocalBaserowTableServiceAggregationSeriesSerializer(serializers.ModelSerializer):
    field_id = serializers.IntegerField()
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceAggregationSeries
        fields = ("order", "aggregation_type", "field_id")


class LocalBaserowTableServiceAggregationGroupBySerializer(serializers.ModelSerializer):
    field_id = serializers.IntegerField()
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceAggregationGroupBy
        fields = ("order", "field_id")
