import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Type, Union

from django.utils.functional import lazy

from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.utils import serialize_validation_errors_recursive
from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.api.fields.serializers import FieldSerializer
from baserow.contrib.database.fields.field_filters import (
    FILTER_TYPE_AND,
    FILTER_TYPE_OR,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.exceptions import ViewOwnershipTypeDoesNotExist
from baserow.contrib.database.views.models import (
    OWNERSHIP_TYPE_COLLABORATIVE,
    View,
    ViewDecoration,
    ViewFilter,
    ViewFilterGroup,
    ViewGroupBy,
    ViewSort,
)
from baserow.contrib.database.views.registries import (
    decorator_type_registry,
    decorator_value_provider_type_registry,
    view_filter_type_registry,
    view_ownership_type_registry,
    view_type_registry,
)

from ..tables.serializers import TableWithoutDataSyncSerializer
from .exceptions import FiltersParamValidationException


class ListQueryParamatersSerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, default=None)
    type = serializers.ChoiceField(
        required=False,
        default=None,
        choices=lazy(view_type_registry.get_types, list)(),
    )


class FieldOptionsField(serializers.Field):
    default_error_messages = {
        "invalid_key": "Field option key must be numeric.",
        "invalid_value": "Must be valid field options.",
    }

    def __init__(self, serializer_class, create_if_missing=True, **kwargs):
        self.serializer_class = serializer_class
        self.create_if_missing = create_if_missing
        self._spectacular_annotation = {
            "field": serializers.DictField(
                child=serializer_class(),
                help_text="An object containing the field id as key and the properties "
                "related to view as value.",
            )
        }
        kwargs["source"] = "*"
        kwargs["read_only"] = False
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        """
        This method only passes the validation if the provided data dict is in the
        correct format. Not if the field id actually exists.

        Example format:
        {
            FIELD_ID: {
                "value": 200
            }
        }

        :param data: The data that needs to be validated.
        :type data: dict
        :return: The validated dict.
        :rtype: dict
        """

        internal = {}
        for key, value in data.items():
            if not (isinstance(key, int) or (isinstance(key, str) and key.isnumeric())):
                self.fail("invalid_key")
            serializer = self.serializer_class(data=value)
            if not serializer.is_valid():
                self.fail("invalid_value")
            internal[int(key)] = serializer.data
        return internal

    def to_representation(self, value):
        """
        If the provided value is a GridView instance we need to fetch the options from
        the database. We can easily use the `get_field_options` of the GridView for
        that and format the dict the way we want.

        If the provided value is a dict it means the field options have already been
        provided and validated once, so we can just return that value. The variant is
        used when we want to validate the input.

        :param value: The prepared value that needs to be serialized.
        :type value: GridView or dict
        :return: A dictionary containing the
        :rtype: dict
        """

        if isinstance(value, View):
            field_options = self.context.get("field_options", None)
            if field_options is None:
                # If the fields are in the context we can pass them into the
                # `get_field_options` call so that they don't have to be fetched from
                # the database again.
                field_options = value.get_field_options(
                    self.create_if_missing, self.context.get("fields")
                )
            return {
                field_options.field_id: self.serializer_class(field_options).data
                for field_options in field_options
            }
        else:
            return value


class ViewFilterSerializer(serializers.ModelSerializer):
    preload_values = serializers.DictField(
        help_text="Can contain unique preloaded values per filter. This is for "
        "example used by the `link_row_has` filter to communicate the display name if "
        "a value is provided.",
        read_only=True,
    )
    group = serializers.IntegerField(
        source="group_id",
        allow_null=True,
        required=False,
        help_text=(
            "The id of the filter group this filter belongs to. "
            "If this is null, the filter is not part of a filter group."
        ),
    )

    class Meta:
        model = ViewFilter
        fields = (
            "id",
            "view",
            "field",
            "type",
            "value",
            "preload_values",
            "group",
        )
        extra_kwargs = {"id": {"read_only": True}}


class CreateViewFilterSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(view_filter_type_registry.get_types, list)(),
        help_text=ViewFilter._meta.get_field("type").help_text,
    )
    group = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text=(
            "The id of the filter group the new filter will belong to. "
            "If this is null, the filter will not be part of a filter group, "
            "but directly part of the view."
        ),
    )

    class Meta:
        model = ViewFilter
        fields = ("field", "type", "value", "group")
        extra_kwargs = {"value": {"default": ""}}


class UpdateViewFilterSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(view_filter_type_registry.get_types, list)(),
        required=False,
        help_text=ViewFilter._meta.get_field("type").help_text,
    )

    class Meta(CreateViewFilterSerializer.Meta):
        model = ViewFilter
        fields = ("field", "type", "value")
        extra_kwargs = {"field": {"required": False}, "value": {"required": False}}


class ViewFilterGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewFilterGroup
        fields = ("id", "filter_type", "view", "parent_group")
        extra_kwargs = {"id": {"read_only": True}}


class CreateViewFilterGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewFilterGroup
        fields = ("filter_type", "parent_group")
        extra_kwargs = {
            "filter_type": {"required": False},
            "parent_group": {"required": False},
        }


class UpdateViewFilterGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewFilterGroup
        fields = ("filter_type",)


class ViewSortSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewSort
        fields = ("id", "view", "field", "order", "type")
        extra_kwargs = {"id": {"read_only": True}}


class CreateViewSortSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewSort
        fields = ("field", "order", "type")
        extra_kwargs = {
            "order": {"default": ViewSort._meta.get_field("order").default},
        }


class UpdateViewSortSerializer(serializers.ModelSerializer):
    class Meta(CreateViewFilterSerializer.Meta):
        model = ViewSort
        fields = ("field", "order", "type")
        extra_kwargs = {
            "field": {"required": False},
            "order": {"required": False},
            "width": {"required": False},
            "type": {"required": False},
        }


class ViewGroupBySerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewGroupBy
        fields = (
            "id",
            "view",
            "field",
            "order",
            "width",
            "type",
        )
        extra_kwargs = {"id": {"read_only": True}}


class CreateViewGroupBySerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewGroupBy
        fields = (
            "field",
            "order",
            "width",
            "type",
        )
        extra_kwargs = {
            "order": {"default": ViewGroupBy._meta.get_field("order").default},
            "width": {"default": ViewGroupBy._meta.get_field("width").default},
            "type": {"default": ViewGroupBy._meta.get_field("type").default},
        }


class UpdateViewGroupBySerializer(serializers.ModelSerializer):
    class Meta(CreateViewFilterSerializer.Meta):
        model = ViewGroupBy
        fields = (
            "field",
            "order",
            "width",
            "type",
        )
        extra_kwargs = {
            "field": {"required": False},
            "order": {"required": False},
            "width": {"required": False},
            "type": {"required": False},
        }


class ViewDecorationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewDecoration
        fields = (
            "id",
            "view",
            "type",
            "value_provider_type",
            "value_provider_conf",
            "order",
        )
        extra_kwargs = {
            "id": {"read_only": True, "required": False},
            "view": {"required": False},
            "type": {"required": False},
            "value_provider_conf": {"required": False},
        }


def _only_empty_dict(value):
    if not (isinstance(value, dict) and not value):
        raise serializers.ValidationError("This field should be an empty object.")


class UpdateViewDecorationSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(decorator_type_registry.get_types, list)(),
        required=False,
        help_text=ViewDecoration._meta.get_field("type").help_text,
    )
    value_provider_type = serializers.ChoiceField(
        choices=lazy(
            lambda: [""] + decorator_value_provider_type_registry.get_types(),
            list,
        )(),
        required=False,
        help_text=ViewDecoration._meta.get_field("value_provider_type").help_text,
    )
    value_provider_conf = serializers.DictField(
        required=False,
        validators=[_only_empty_dict],
        help_text=ViewDecoration._meta.get_field("value_provider_conf").help_text,
    )

    class Meta:
        model = ViewDecoration
        fields = ("type", "value_provider_type", "value_provider_conf", "order")
        extra_kwargs = {
            "order": {"required": False},
        }


class CreateViewDecorationSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(decorator_type_registry.get_types, list)(),
        required=True,
        help_text=ViewDecoration._meta.get_field("type").help_text,
    )
    value_provider_type = serializers.ChoiceField(
        choices=lazy(
            lambda: [""] + decorator_value_provider_type_registry.get_types(),
            list,
        )(),
        default="",
        required=False,
        help_text=ViewDecoration._meta.get_field("value_provider_type").help_text,
    )
    value_provider_conf = serializers.DictField(
        required=False,
        default=dict,
        validators=[_only_empty_dict],
        help_text=ViewDecoration._meta.get_field("value_provider_conf").help_text,
    )

    class Meta:
        model = ViewDecoration
        fields = ("type", "value_provider_type", "value_provider_conf", "order")
        extra_kwargs = {
            "order": {"required": False},
        }


class ViewSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    table = TableWithoutDataSyncSerializer()
    filters = ViewFilterSerializer(many=True, source="viewfilter_set", required=False)
    filter_groups = ViewFilterGroupSerializer(many=True, required=False)
    sortings = ViewSortSerializer(many=True, source="viewsort_set", required=False)
    group_bys = ViewGroupBySerializer(
        many=True, source="viewgroupby_set", required=False
    )
    decorations = ViewDecorationSerializer(
        many=True, source="viewdecoration_set", required=False
    )
    show_logo = serializers.BooleanField(required=False)
    ownership_type = serializers.CharField()
    owned_by_id = serializers.IntegerField(required=False)

    class Meta:
        model = View
        fields = (
            "id",
            "table_id",
            "name",
            "order",
            "type",
            "table",
            "filter_type",
            "filters",
            "filter_groups",
            "sortings",
            "group_bys",
            "decorations",
            "filters_disabled",
            "public_view_has_password",
            "show_logo",
            "allow_public_export",
            "ownership_type",
            "owned_by_id",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "table_id": {"read_only": True},
            "public_view_has_password": {"read_only": True},
            "ownership_type": {"read_only": True},
            "owned_by_id": {"read_only": True},
        }

    def __init__(self, instance=None, *args, **kwargs):
        context = kwargs.setdefault("context", {})
        context["include_filters"] = kwargs.pop("filters", False)
        context["include_sortings"] = kwargs.pop("sortings", False)
        context["include_decorations"] = kwargs.pop("decorations", False)
        context["include_group_bys"] = kwargs.pop("group_bys", False)
        enhance_objects_by_view_ownership = kwargs.pop(
            "enhance_objects_by_view_ownership", True
        )
        # If the provided view object(s) must be enhanced by the view type, then
        # correctly call those methods. The view ownership type can be responsible for
        # adding or omitting data about the view. Making this call in the serializer
        # makes sure that the user only receives data about the view that they are
        # permitted to see, according to the ownership type.
        if enhance_objects_by_view_ownership and "user" in context:
            if isinstance(instance, list):
                instance = view_ownership_type_registry.prepare_views_of_different_types_for_user(
                    context["user"], instance
                )
            else:
                instance = (
                    view_ownership_type_registry.prepare_views_of_different_types_for_user(
                        context["user"], [instance]
                    )
                )[0]
        super().__init__(instance, *args, **kwargs)

    def to_representation(self, instance):
        # We remove the fields in to_representation rather than __init__ as otherwise
        # drf-spectacular will not know that filters, sortings and decorations exist as
        # optional return fields.
        # This way the fields are still dynamic and also show up in the OpenAPI
        # specification.
        if not self.context["include_filters"]:
            self.fields.pop("filters", None)
            self.fields.pop("filter_groups", None)

        if not self.context["include_sortings"]:
            self.fields.pop("sortings", None)

        if not self.context["include_decorations"]:
            self.fields.pop("decorations", None)

        if not self.context["include_group_bys"]:
            self.fields.pop("group_bys", None)

        return super().to_representation(instance)

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return view_type_registry.get_by_model(instance.specific_class).type


class CreateViewSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(view_type_registry.get_types, list)(), required=True
    )
    ownership_type = serializers.ChoiceField(
        choices=lazy(view_ownership_type_registry.get_types, list)(),
        default=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    class Meta:
        model = View
        fields = ("name", "type", "ownership_type", "filter_type", "filters_disabled")


class UpdateViewSerializer(serializers.ModelSerializer):
    MAX_PUBLIC_VIEW_PASSWORD_LENGTH = 256
    MIN_PUBLIC_VIEW_PASSWORD_LENGTH = 8

    public_view_password = serializers.CharField(
        required=False,
        allow_blank=True,
        min_length=MIN_PUBLIC_VIEW_PASSWORD_LENGTH,
        max_length=MAX_PUBLIC_VIEW_PASSWORD_LENGTH,
        help_text="The new password or an empty string to remove any previous "
        "password from the view and make it publicly accessible again.",
    )

    def to_internal_value(self, data):
        internal_value = super().to_internal_value(data)

        # Store the hashed password in the database if provided. An empty string
        # means that the password protection is disabled.
        raw_public_view_password = internal_value.pop("public_view_password", None)
        if raw_public_view_password is not None or "public" in data:
            internal_value["public_view_password"] = (
                View.make_password(raw_public_view_password)
                if raw_public_view_password
                else ""  # nosec b105
            )

        return internal_value

    def validate_ownership_type(self, value):
        try:
            view_ownership_type_registry.get(value)
        except ViewOwnershipTypeDoesNotExist:
            allowed_ownerships = ",".join(
                "'%s'" % v for v in view_ownership_type_registry.get_types()
            )
            raise serializers.ValidationError(
                f"Ownership type must be one of the above: {allowed_ownerships}."
            )
        return value

    class Meta:
        ref_name = "view_update"
        model = View
        fields = (
            "name",
            "filter_type",
            "filters_disabled",
            "public_view_password",
            "ownership_type",
        )
        extra_kwargs = {
            "name": {"required": False},
            "filter_type": {"required": False},
            "filters_disabled": {"required": False},
        }


class OrderViewsSerializer(serializers.Serializer):
    view_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="View ids in the desired order.",
        min_length=1,
    )


class PublicViewAuthRequestSerializer(serializers.Serializer):
    password = serializers.CharField()


class PublicViewAuthResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()


class PublicViewSortSerializer(serializers.ModelSerializer):
    view = serializers.SlugField(source="view.slug")

    class Meta:
        model = ViewSort
        fields = ("id", "view", "field", "order", "type")
        extra_kwargs = {"id": {"read_only": True}}


class PublicViewGroupBySerializer(serializers.ModelSerializer):
    view = serializers.SlugField(source="view.slug")

    class Meta:
        model = ViewGroupBy
        fields = (
            "id",
            "view",
            "field",
            "order",
            "width",
            "type",
        )
        extra_kwargs = {"id": {"read_only": True}}


class PublicViewTableSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    database_id = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.INT)
    def get_id(self, instance):
        return PUBLIC_PLACEHOLDER_ENTITY_ID

    @extend_schema_field(OpenApiTypes.INT)
    def get_database_id(self, instance):
        return PUBLIC_PLACEHOLDER_ENTITY_ID


class PublicViewSerializer(serializers.ModelSerializer):
    id = serializers.SlugField(source="slug")
    table = PublicViewTableSerializer()
    type = serializers.SerializerMethodField()
    sortings = serializers.SerializerMethodField()
    group_bys = serializers.SerializerMethodField()
    show_logo = serializers.BooleanField(required=False)

    @extend_schema_field(PublicViewSortSerializer(many=True))
    def get_sortings(self, instance):
        sortings = PublicViewSortSerializer(
            instance=instance.viewsort_set.filter(field__in=self.context["fields"]),
            many=True,
        )
        return sortings.data

    @extend_schema_field(PublicViewGroupBySerializer(many=True))
    def get_group_bys(self, instance):
        view_type = view_type_registry.get_by_model(instance.specific_class)
        if view_type.can_group_by:
            group_bys = PublicViewGroupBySerializer(
                instance=instance.viewgroupby_set.filter(
                    field__in=self.context["fields"]
                ),
                many=True,
            )
            return group_bys.data
        else:
            return []

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return view_type_registry.get_by_model(instance.specific_class).type

    class Meta:
        model = View
        fields = (
            "id",
            "table",
            "name",
            "order",
            "type",
            "sortings",
            "group_bys",
            "public",
            "slug",
            "show_logo",
            "allow_public_export",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "slug": {"read_only": True},
        }


class PublicFieldSerializer(FieldSerializer):
    table_id = serializers.SerializerMethodField()
    database_id = serializers.SerializerMethodField()
    workspace_id = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.INT)
    def get_table_id(self, instance):
        return PUBLIC_PLACEHOLDER_ENTITY_ID

    @extend_schema_field(OpenApiTypes.INT)
    def get_database_id(self, instance):
        return PUBLIC_PLACEHOLDER_ENTITY_ID

    @extend_schema_field(OpenApiTypes.INT)
    def get_workspace_id(self, instance):
        return PUBLIC_PLACEHOLDER_ENTITY_ID


class PublicViewInfoSerializer(serializers.Serializer):
    # get_fields is an actual method on serializers.Serializer so we can't override it.
    fields = serializers.SerializerMethodField(method_name="get_public_fields")
    view = serializers.SerializerMethodField()

    # @TODO show correct API docs discriminated by field type.
    @extend_schema_field(PublicFieldSerializer(many=True))
    def get_public_fields(self, instance):
        return [
            field_type_registry.get_serializer(field, PublicFieldSerializer).data
            for field in self.context["fields"]
        ]

    # @TODO show correct API docs discriminated by field type.
    @extend_schema_field(PublicViewSerializer)
    def get_view(self, instance):
        return view_type_registry.get_serializer(
            instance, PublicViewSerializer, context=self.context
        ).data

    def __init__(self, *args, **kwargs):
        kwargs["context"] = kwargs.get("context", {})
        kwargs["context"]["fields"] = kwargs.pop("fields", [])
        super().__init__(instance=kwargs.pop("view", None), *args, **kwargs)


class FieldWithFiltersAndSortsSerializer(FieldSerializer):
    filters = ViewFilterSerializer(many=True, source="viewfilter_set")
    groups = ViewFilterGroupSerializer(many=True, source="filter_groups")
    sortings = ViewSortSerializer(many=True, source="viewsort_set")
    group_bys = ViewGroupBySerializer(many=True, source="viewgroupby_set")

    class Meta(FieldSerializer.Meta):
        fields = FieldSerializer.Meta.fields + ("filters", "sortings", "group_bys")


class PublicViewFilterSerializer(serializers.Serializer):
    field = serializers.IntegerField(help_text="The id of the field to filter on.")
    type = serializers.CharField(help_text="The filter type.")
    value = serializers.CharField(allow_blank=True, help_text="The filter value.")

    def to_internal_value(self, data: Dict[str, any]):
        """
        Ensures that the `value` is sanitized of characters which can
        result in an error upon insertion to the database, such as the
        NUL character.

        :param data: the prepared dict before `value` sanitization.
        :return: the prepared dict, with the `value` sanitized.
        """

        from baserow.contrib.database.views.filters import sanitize_adhoc_filter_value

        if value := data.get("value"):
            data["value"] = sanitize_adhoc_filter_value(value)
        return super().to_internal_value(data)


class PublicViewFilterUserFieldNamesSerializer(PublicViewFilterSerializer):
    field = serializers.CharField(help_text="The name of the field to filter on.")


class RecursiveField(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data

    def to_internal_value(self, data):
        serializer = self.parent.parent.__class__(data=data, context=self.context)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class PublicViewFiltersSerializer(serializers.Serializer):
    filter_type = serializers.ChoiceField(choices=[FILTER_TYPE_AND, FILTER_TYPE_OR])
    filters = serializers.ListField(
        child=PublicViewFilterSerializer(),
        required=False,
        allow_empty=True,
        help_text="The list of filters that should be applied in this group/public "
        "view.",
    )
    groups = RecursiveField(many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("user_field_names", False):
            self.fields["filters"].child = PublicViewFilterUserFieldNamesSerializer()


def validate_api_grouped_filters(
    api_filters: Union[str, Dict],
    exception_to_raise: Type[Exception] = FiltersParamValidationException,
    user_field_names: Optional[bool] = False,
    deserialize_filters: bool = True,
) -> Dict[str, Any]:
    """
    Validates the provided serialized view filters and returns the validated
    data. The serialized view filters should be a JSON string that can be
    deserialized into a list of filters and/or group of filters. Group of
    filters can nest other groups of filters. Look at
    `PublicViewFiltersSerializer` for more info about the structure.

    :param api_filters: A serialized JSON string, or a deserialized dictionary,
        depending on the value of `deserialize_filters`.
    :param exception_to_raise: The exception that should be raised if the
        provided filters are not valid.
    :param user_field_names: Use field names instead of field ids in the
        serialized filters.
    :param deserialize_filters: If True, the provided `api_filters` will be
        deserialized into a dictionary. If False, the provided `api_filters`
        will be used as is.
    :return: The validated dict containing the filters and the filter groups.
    """

    advanced_filters = api_filters
    if deserialize_filters:
        try:
            advanced_filters = json.loads(api_filters)
        except json.JSONDecodeError:
            raise exception_to_raise(
                {
                    "error": "The provided filters are not valid JSON.",
                    "code": "invalid_json",
                }
            )

    serializer = PublicViewFiltersSerializer(
        data=advanced_filters, context={"user_field_names": user_field_names}
    )
    if not serializer.is_valid():
        detail = serialize_validation_errors_recursive(serializer.errors)
        raise exception_to_raise(detail)

    return serializer.validated_data


def serialize_group_by_metadata(
    group_by_metadata: Dict[Field, List[Dict[str, Any]]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Serializes the structure generated by the `get_group_by_metadata_in_rows`
    ViewHandler method. The structure looks like:

    ```
    {
        field_instance: [
            {"count": 1, "field_{id}": Decimal('1.00')}
        ]
    }
    ```

    The key of the dict, and the `field_{id}` will be replaced with serialized values
    that can be used as API response.

    :param group_by_metadata: The object that must be serialized
    :return: The serialized object.
    """

    serializer_mapping = {}

    for field in group_by_metadata.keys():
        field_type = field_type_registry.get_by_model(field.specific_class)
        field_name = field.db_column
        field_serializer = field_type.get_group_by_serializer_field(field)
        serializer_mapping[field_name] = field_serializer

    serialized_data = defaultdict(list)

    for field, data in group_by_metadata.items():
        for entry in data:
            serialized_entry = {"count": entry["count"]}
            for key, value in entry.items():
                if key in serializer_mapping:
                    # This is the same behavior as a normal serializer, so that's
                    # what we need in the frontend to compare the two values.
                    if value is None:
                        serialized_entry[key] = None
                    else:
                        serialized_entry[key] = serializer_mapping[
                            key
                        ].to_representation(value)
            serialized_data[field.db_column].append(serialized_entry)

    return serialized_data
