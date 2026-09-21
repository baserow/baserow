from rest_framework import serializers

from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
    LocalBaserowTableServiceAggregationSortBy,
)


class LocalBaserowTableServiceAggregationSeriesSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    field_id = serializers.IntegerField(allow_null=True)
    trashed = serializers.BooleanField(
        source="field.trashed",
        read_only=True,
        default=False,
        help_text="An aggregation series is considered trashed if "
        "the field it's associated with is trashed.",
    )

    class Meta:
        model = LocalBaserowTableServiceAggregationSeries
        fields = ("id", "aggregation_type", "field_id", "trashed")


class LocalBaserowTableServiceAggregationGroupBySerializer(serializers.ModelSerializer):
    field_id = serializers.IntegerField(allow_null=True)
    order = serializers.IntegerField(read_only=True)
    trashed = serializers.BooleanField(
        source="field.trashed",
        read_only=True,
        default=False,
        help_text="An aggregation group by is considered trashed if "
        "the field it's associated with is trashed.",
    )

    class Meta:
        model = LocalBaserowTableServiceAggregationGroupBy
        fields = ("order", "field_id", "trashed")


class LocalBaserowTableServiceAggregationSortBySerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceAggregationSortBy
        fields = ("order", "sort_on", "reference", "direction")
