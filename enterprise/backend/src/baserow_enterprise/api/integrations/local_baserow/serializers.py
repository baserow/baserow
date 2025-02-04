from rest_framework import serializers

from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
)


class LocalBaserowTableServiceAggregationSeriesSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceAggregationSeries
        fields = ("id", "order", "field", "aggregation_type")


class LocalBaserowTableServiceAggregationGroupBySerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceAggregationGroupBy
        fields = ("id", "order", "field")
