from django.utils.functional import lazy

from rest_framework import serializers

from baserow.contrib.database.views.models import FILTER_TYPES, ViewFilter
from baserow.contrib.database.views.registries import view_filter_type_registry


class SelectColorValueProviderConfSerializer(serializers.Serializer):
    field_id = serializers.IntegerField(
        allow_null=True,
        help_text=(
            "An id of a select field of the table. "
            "The value provider return the color of the selected option for each row."
        ),
    )


class ConditionalColorValueProviderConfColorFilterSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="A unique identifier for this condition.")
    field = serializers.IntegerField(
        allow_null=True,
        help_text=ViewFilter._meta.get_field("field").help_text,
    )
    type = serializers.ChoiceField(
        choices=lazy(view_filter_type_registry.get_types, list)(),
        allow_null=True,
        help_text=ViewFilter._meta.get_field("type").help_text,
    )
    value = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text=ViewFilter._meta.get_field("field").help_text,
    )
    group = serializers.CharField(
        allow_null=True,
        required=False,
        help_text=(
            "The id of the filter group this filter belongs to. "
            "If this is null, the filter is not part of a filter group."
        ),
    )

    def validate(self, attrs):
        if attrs.get("value") is None:
            attrs["value"] = ""
        return attrs


class ConditionalColorValueProviderConfColorFilterGroupSerializer(
    serializers.Serializer
):
    id = serializers.CharField(help_text="A unique identifier for this condition.")
    filter_type = serializers.ChoiceField(
        choices=FILTER_TYPES,
        default="AND",
        help_text="The boolean operator used to group all conditions.",
    )
    parent_group = serializers.CharField(
        help_text="The id of the parent filter group.",
        required=False,
        allow_null=True,
    )


class ConditionalColorValueProviderConfColorSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="A unique identifier for this condition.")
    color = serializers.CharField(
        help_text="The color the decorator should take if the defined conditions apply."
    )
    filters = ConditionalColorValueProviderConfColorFilterSerializer(
        many=True,
        help_text=(
            "A list of conditions that the row must meet to get the selected color. "
            "This list of conditions can be empty, in that case, "
            "this color will always match the row values."
        ),
    )
    filter_groups = ConditionalColorValueProviderConfColorFilterGroupSerializer(
        required=False,
        many=True,
        help_text=(
            "A list of filter groups that the row must meet to get the selected color. "
        ),
    )
    operator = serializers.ChoiceField(
        choices=FILTER_TYPES,
        default="AND",
        help_text="The boolean operator used to group all conditions.",
    )

    def validate(self, data):
        """
        Ensure every filter has a valid reference to a group.
        """

        group_ids = set([None])
        for group in data.get("filter_groups", []):
            group_ids.add(group["id"])
            if group.get("parent_group", None) not in group_ids:
                raise serializers.ValidationError(
                    "Filter group references a non-existent parent group."
                )

        for filter in data["filters"]:
            group_id = filter.get("group", None)
            if group_id is not None and group_id not in group_ids:
                raise serializers.ValidationError(
                    "Filter references a non-existent group."
                )

        return data


class ConditionalColorValueProviderConfColorsSerializer(serializers.Serializer):
    colors = ConditionalColorValueProviderConfColorSerializer(
        many=True,
        help_text=(
            "A list of color items. For each row, the value provider try to "
            "match the defined colors one by one in the given order. "
            "The first matching color is returned to the decorator."
        ),
    )
