from django.utils.functional import lazy

from rest_framework import serializers

from baserow.contrib.database.views.models import GridViewFieldOptions
from baserow.contrib.database.views.registries import view_aggregation_type_registry


def get_allowed_aggregation_types():
    all_type_names = view_aggregation_type_registry.get_types()

    def is_allowed(agg_type_name: str) -> bool:
        agg_type = view_aggregation_type_registry.get(agg_type_name)
        return agg_type.allowed_in_view

    return [
        agg_type_name for agg_type_name in all_type_names if is_allowed(agg_type_name)
    ]


class GridViewFieldOptionsSerializer(serializers.ModelSerializer):
    aggregation_raw_type = serializers.ChoiceField(
        choices=lazy(get_allowed_aggregation_types, list)(),
        help_text=GridViewFieldOptions._meta.get_field(
            "aggregation_raw_type"
        ).help_text,
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = GridViewFieldOptions
        fields = (
            "width",
            "hidden",
            "order",
            "aggregation_type",
            "aggregation_raw_type",
        )


class GridViewFilterSerializer(serializers.Serializer):
    field_ids = serializers.ListField(
        allow_empty=False,
        required=False,
        default=None,
        child=serializers.IntegerField(),
        help_text="Only the fields related to the provided ids are added to the "
        "response. If None are provided all fields will be returned.",
    )
    row_ids = serializers.ListField(
        allow_empty=False,
        child=serializers.IntegerField(),
        help_text="Only rows related to the provided ids are added to the response.",
    )


class GridViewGroupByDataGroupSerializer(serializers.Serializer):
    path = serializers.DictField(
        help_text=(
            "Mapping of group-by field db_column names to the serialized group "
            "value at every depth from 0 up to this group's depth."
        )
    )
    depth = serializers.IntegerField(
        help_text="Zero-based depth of this group in the group-by hierarchy."
    )
    row_count = serializers.IntegerField(
        help_text="Number of leaf rows descending from this group."
    )
    children_count = serializers.IntegerField(
        required=False,
        help_text="Number of immediate sub-groups. Omitted at leaf depth.",
    )
    sibling_index = serializers.IntegerField(
        help_text="Zero-based index of this group among its siblings."
    )
    row_offset = serializers.IntegerField(
        help_text=(
            "Absolute offset of this group's first descendant row in the full "
            "grouped row order."
        )
    )


class GridViewGroupByDataPageSerializer(serializers.Serializer):
    parent = serializers.DictField(
        help_text="The serialized parent group path requested for this page."
    )
    groups = GridViewGroupByDataGroupSerializer(many=True)
    offset = serializers.IntegerField()
    limit = serializers.IntegerField()
    group_count = serializers.IntegerField()


class GridViewGroupByDataSerializer(serializers.Serializer):
    pages = GridViewGroupByDataPageSerializer(many=True)
    truncated = serializers.BooleanField(
        required=False,
        help_text=(
            "Whether descendant loading stopped early because the response page or "
            "group cap was reached."
        ),
    )
