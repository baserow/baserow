from rest_framework import serializers

from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceSort,
)
from baserow.core.formula.serializers import FormulaSerializerField


class LocalBaserowTableServiceSortSerializer(serializers.ModelSerializer):
    order = serializers.IntegerField(read_only=True)
    trashed = serializers.BooleanField(
        source="field.trashed",
        read_only=True,
        help_text="A sort is considered trashed if "
        "the field it's associated with is trashed.",
    )

    class Meta:
        model = LocalBaserowTableServiceSort
        fields = ("id", "field", "order", "trashed", "order_by")


class LocalBaserowTableServiceSortSerializerMixin(serializers.Serializer):
    """
    A serializer mixin for services which implement the local Baserow sortable mixin.
    It ensures that when serialize the service, *all* sortings (including those pointing
    to trashed fields) are serialized.
    """

    def to_representation(self, instance):
        if isinstance(instance, dict):
            return instance

        representation = super().to_representation(instance)
        representation["sortings"] = LocalBaserowTableServiceSortSerializer(
            instance.service_sorts.all(),
            many=True,
        ).data
        return representation

    def to_internal_value(self, data):
        sortings = data.pop("sortings", None)
        data = super().to_internal_value(data)
        if sortings is not None:
            data["service_sorts"] = [
                LocalBaserowTableServiceSortSerializer().to_internal_value(ss)
                for ss in sortings
            ]
        return data


class LocalBaserowTableServiceFilterSerializer(serializers.ModelSerializer):
    value = FormulaSerializerField(
        help_text="A formula for the filter's value.",
    )
    value_is_formula = serializers.BooleanField(
        default=False, help_text="Indicates whether the value is a formula or not."
    )
    trashed = serializers.BooleanField(
        source="field.trashed",
        read_only=True,
        help_text="A filter is considered trashed if "
        "the field it's associated with is trashed.",
    )
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LocalBaserowTableServiceFilter
        fields = (
            "id",
            "order",
            "field",
            "type",
            "value",
            "trashed",
            "value_is_formula",
        )


class LocalBaserowTableServiceFilterSerializerMixin(serializers.Serializer):
    """
    A serializer mixin for services which implement the local Baserow filterable mixin.
    It ensures that when serialize the service, *all* filters (including those pointing
    to trashed fields) are serialized.
    """

    def to_representation(self, instance):
        if isinstance(instance, dict):
            return instance

        representation = super().to_representation(instance)
        representation["filters"] = LocalBaserowTableServiceFilterSerializer(
            instance.service_filters.all(),
            many=True,
        ).data
        return representation

    def to_internal_value(self, data):
        filters = data.pop("filters", None)
        data = super().to_internal_value(data)
        if filters is not None:
            data["service_filters"] = [
                LocalBaserowTableServiceFilterSerializer().to_internal_value(sf)
                for sf in filters
            ]
        return data


class LocalBaserowTableServiceFieldMappingSerializer(serializers.Serializer):
    field_id = serializers.IntegerField(
        help_text="The primary key of the associated database table field."
    )
    enabled = serializers.BooleanField(
        help_text="Indicates whether the field mapping is enabled or not."
    )
    value = FormulaSerializerField()
