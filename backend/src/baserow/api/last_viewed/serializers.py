from typing import Dict, Optional, Set

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from baserow.api.pagination import KeysetCursorField
from baserow.api.serializers import CommaSeparatedIntegerValuesField
from baserow.core.last_viewed.handler import LastViewedListItem
from baserow.core.registries import (
    application_type_registry,
    last_viewed_item_type_registry,
)
from baserow.core.utils import split_comma_separated_string

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class LastViewedItemsQuerySerializer(serializers.Serializer):
    workspace_ids = CommaSeparatedIntegerValuesField(
        required=False,
        help_text="Comma separated ids of the workspaces to list items of. "
        "Workspaces the user is not a member of are ignored.",
    )
    types = serializers.CharField(
        required=False,
        help_text="Comma separated item types to list, like `builder_page`. A type "
        "with sub types can be limited to one of them with `type:sub_type`, like "
        "`database_view:grid`.",
    )
    limit = serializers.IntegerField(
        default=DEFAULT_LIMIT,
        min_value=1,
        max_value=MAX_LIMIT,
        help_text="Maximum number of items to return.",
    )
    cursor = KeysetCursorField(
        required=False,
        help_text="The `next_cursor` of the previous page, omitted for the first page.",
    )

    def validate_workspace_ids(self, value):
        return [int(workspace_id) for workspace_id in value]

    def validate_types(self, value) -> Dict[str, Optional[Set[str]]]:
        type_filters: Dict[str, Optional[Set[str]]] = {}
        for token in split_comma_separated_string(value):
            type_name, _, sub_type = token.partition(":")
            if type_name not in last_viewed_item_type_registry.get_types():
                raise serializers.ValidationError(
                    f"`{type_name}` is not a valid item type."
                )
            if not sub_type:
                type_filters[type_name] = None
                continue

            item_type = last_viewed_item_type_registry.get(type_name)
            if sub_type not in item_type.get_sub_types():
                raise serializers.ValidationError(
                    f"`{sub_type}` is not a valid sub type of `{type_name}`."
                )
            # A whole type mentioned earlier already covers every sub type.
            if type_name in type_filters and type_filters[type_name] is None:
                continue
            type_filters.setdefault(type_name, set()).add(sub_type)
        return type_filters


def get_last_viewed_item_serializer_mapping():
    """
    Built lazily because the item types register themselves while the Django
    applications are being initialized.
    """

    return {
        item_type.type: item_type.get_serializer_class(
            meta_ref_name=f"LastViewed{item_type.model_class.__name__}Item"
        )
        for item_type in last_viewed_item_type_registry.get_all()
    }


class LastViewedItemApplicationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return application_type_registry.get_by_model(instance.specific_class).type


class LastViewedItemWorkspaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class LastViewedItemSerializer(serializers.Serializer):
    """
    Serializes a `LastViewedListItem`. The nested `item` is produced by the
    serializer class of the registered type, because the four leaf models share no
    common base.
    """

    type = serializers.CharField(source="item_type.type")
    sub_type = serializers.CharField(
        allow_null=True,
        help_text="Set for polymorphic types, like the view type of a database view.",
    )
    last_viewed = serializers.DateTimeField(source="row.last_viewed")
    application = LastViewedItemApplicationSerializer(source="row.application")
    workspace = LastViewedItemWorkspaceSerializer(source="row.workspace")
    item = serializers.SerializerMethodField(
        help_text="The `id` and `name` of the item, plus what the type adds. A "
        "database view also carries its `table` (`id`, `name`)."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Generating a serializer class is not free, so one is kept per type for
        # the lifetime of this serializer, which is a single response.
        self._item_serializer_classes = {}

    @extend_schema_field(
        PolymorphicProxySerializer(
            component_name="PolymorphicLastViewedItem",
            serializers=get_last_viewed_item_serializer_mapping,
            # The type is a sibling of this field instead of one of its own
            # properties, so the schema is a plain union.
            resource_type_field_name=None,
        )
    )
    def get_item(self, obj: LastViewedListItem) -> dict:
        serializer_class = self._item_serializer_classes.get(obj.item_type.type)
        if serializer_class is None:
            serializer_class = obj.item_type.get_serializer_class(
                meta_ref_name=f"LastViewed{obj.item_type.model_class.__name__}Item"
            )
            self._item_serializer_classes[obj.item_type.type] = serializer_class
        return serializer_class(obj.instance, context=self.context).data


class LastViewedItemsResponseSerializer(serializers.Serializer):
    results = LastViewedItemSerializer(many=True)
    next_cursor = serializers.CharField(
        allow_null=True,
        help_text="Pass as `cursor` to get the next page, `null` when no more "
        "items follow.",
    )
