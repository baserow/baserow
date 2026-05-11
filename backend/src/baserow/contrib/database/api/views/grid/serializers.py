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


class GridViewGroupTreeNodeSerializer(serializers.Serializer):
    path = serializers.DictField(
        help_text=(
            "Mapping of group-by field db_column names to the deserialized "
            "group value at every depth from 0 up to this node's depth."
        )
    )
    depth = serializers.IntegerField(
        help_text="Zero-based depth of this node in the group-by hierarchy."
    )
    row_count = serializers.IntegerField(
        help_text=(
            "Number of leaf rows (matching the view's filters) descending "
            "from this node, regardless of any client-side collapse state."
        )
    )
    children_count = serializers.IntegerField(
        required=False,
        help_text=(
            "Number of immediate sub-groups one depth below this node. "
            "Omitted at the deepest depth (leaf nodes have no sub-groups). "
            "The frontend uses this to reserve layout space for unloaded "
            "subtrees while their children are being fetched."
        ),
    )


class GridViewGroupTreeSerializer(serializers.Serializer):
    nodes = GridViewGroupTreeNodeSerializer(
        many=True,
        help_text=(
            "Flat list of group nodes ordered for display. Children of a node "
            "always immediately follow that node."
        ),
    )
    truncated = serializers.BooleanField(
        help_text=(
            "True when the tree exceeds the configured node cap. The "
            "frontend should fall back to uniform-height scrollbar math."
        )
    )
    total_nodes = serializers.IntegerField(
        help_text="Total number of group nodes across all depths."
    )
