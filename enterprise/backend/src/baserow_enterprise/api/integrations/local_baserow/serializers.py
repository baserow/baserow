from rest_framework import serializers

from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
    LocalBaserowTableServiceAggregationSortBy,
)


class LocalBaserowTableServiceAggregationSeriesSerializer(serializers.ModelSerializer):
    field_id = serializers.IntegerField(allow_null=True)
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceAggregationSeries
        fields = ("order", "aggregation_type", "field_id")


class LocalBaserowTableServiceAggregationGroupBySerializer(serializers.ModelSerializer):
    field_id = serializers.IntegerField(allow_null=True)
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceAggregationGroupBy
        fields = ("order", "field_id")


class LocalBaserowTableServiceAggregationSortBySerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceAggregationSortBy
        fields = ("order", "sort_on", "reference", "direction")
