from typing import Any, Dict, List, Optional, Set, Type

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.views.operations import (
    CreateViewDecorationOperationType,
    CreateViewFilterGroupOperationType,
    CreateViewFilterOperationType,
    CreateViewGroupByOperationType,
    CreateViewSortOperationType,
    ReadViewDefaultValuesOperationType,
    UpdateViewDefaultValuesOperationType,
    UpdateViewFieldOptionsOperationType,
    UpdateViewOperationType,
)
from baserow.contrib.database.views.registries import (
    ViewType,
    decorator_type_registry,
    decorator_value_provider_type_registry,
    view_type_registry,
)
from baserow.core.registries import OperationType
from baserow.core.registry import Instance, Registry

from .exceptions import (
    DecoratorTypeDoesNotExist,
    DecoratorValueProviderTypeDoesNotExist,
)
from .models import (
    View,
    ViewDecoration,
    ViewDefaultValue,
    ViewFilter,
    ViewFilterGroup,
    ViewGroupBy,
    ViewSort,
)

FieldOptionsDict = Dict[int, Dict[str, Any]]


class ViewConfigurationCopyCategoryType(Instance):
    """
    One copyable piece of view configuration, the filters or sorts for example. The
    `type` is part of the public API contract and must match the category key used by
    the web-frontend.

    Categories apply their configuration with bulk ORM operations and without sending
    granular realtime signals, so that connected clients can be sent a single event
    with the complete new view state after all categories have been applied.
    """

    operation_types: List[Type[OperationType]] = []
    """
    The operations a user needs on a view to copy this category from or into it.
    They're checked symmetrically on the source and the destination because copying
    is a configure level act, and because the view ownership managers hide
    configuration from users that lack these same write operations, restricted views
    hide the filters from users without `CreateViewFilterOperationType` for example,
    so a read operation alone would leak configuration that the interface hides.
    """

    def is_supported(self, view_type: ViewType) -> bool:
        """
        A category can only be copied when both the source and destination view type
        support it.

        :param view_type: The view type to check the support for.
        :return: True if the view type supports this category.
        """

        raise NotImplementedError

    def export_configuration(
        self, view: View, cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Returns a JSON serializable snapshot, including primary keys so that an undo
        can restore the exact same objects.

        :param view: The specific view to export the configuration of.
        :param cache: A dict shared by all categories of one export to avoid
            duplicate queries.
        :return: The exported configuration of this category.
        """

        raise NotImplementedError

    def apply_configuration(
        self,
        view: View,
        configuration: Dict[str, Any],
        user: Optional[AbstractUser] = None,
        preserve_ids: bool = False,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[FieldOptionsDict]:
        """
        Replaces this category's configuration of the view with an exported one.

        :param view: The specific view to apply the configuration to.
        :param configuration: A configuration previously returned by
            `export_configuration`. It can have been JSON round-tripped, so integer
            dict keys may have become strings.
        :param user: The user on whose behalf the configuration is applied.
        :param preserve_ids: If True, the objects are recreated with the primary keys
            from the configuration, which undo/redo relies on so that other clients
            keep referencing valid ids.
        :param cache: A dict shared by all categories of one apply to avoid duplicate
            queries.
        :return: Optionally a field options dict that is not applied by the category
            itself, but merged with those of the other categories by the caller and
            applied in a single batch.
        """

        raise NotImplementedError

    def after_applied(self, view: View):
        """
        Hook that is called after the configuration of every category has been
        applied to the view.

        :param view: The specific view that the configuration was applied to.
        """


class ViewConfigurationCopyCategoryTypeRegistry(Registry):
    name = "view_configuration_copy_category"


view_configuration_copy_category_type_registry = (
    ViewConfigurationCopyCategoryTypeRegistry()
)


def _including_trashed_fields(model, view: View):
    """
    The default managers of the filter, sort and group by models hide rows whose field
    is trashed, but that configuration is deliberately kept until the field is
    permanently deleted, so it restores together with the field. Exports must snapshot
    those hidden rows and the replacing deletes must remove them, otherwise they would
    either be lost by the group cascade delete or survive a copy and resurface when the
    field is restored.

    :param model: The filter, sort or group by model class to query.
    :param view: The view to fetch the objects of.
    :return: A trash inclusive queryset of the view's objects.
    """

    return model._base_manager.filter(view=view, view__trashed=False)


def _existing_field_ids(view: View, cache: Optional[Dict[str, Any]]) -> Set[int]:
    """
    The fields that filters, sorts and field options may reference. Trashed fields are
    included because their view configuration is kept until they are permanently
    deleted, but fields that have been permanently deleted since a configuration was
    exported must be skipped.

    :param view: The view whose table's fields are returned.
    :param cache: A dict shared within one export or apply to avoid duplicate
        queries.
    :return: The ids of all existing fields in the view's table.
    """

    if cache is None:
        cache = {}

    cache_key = f"existing_field_ids_{view.id}"
    if cache_key not in cache:
        cache[cache_key] = set(
            Field.objects_and_trash.filter(table_id=view.table_id).values_list(
                "id", flat=True
            )
        )
    return cache[cache_key]


class FieldOptionsCopyCategoryType(ViewConfigurationCopyCategoryType):
    """
    Base class for categories that copy a single key of the view's field options, the
    `hidden` state of every field for example.
    """

    field_option_key = None
    operation_types = [UpdateViewFieldOptionsOperationType]

    def is_supported(self, view_type: ViewType) -> bool:
        return self.field_option_key in view_type.field_options_allowed_fields

    def export_configuration(
        self, view: View, cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if cache is None:
            cache = {}

        cache_key = f"field_options_{view.id}"
        if cache_key not in cache:
            view.get_field_options(create_if_missing=True)
            view_type = view_type_registry.get_by_model(view.specific_class)
            cache[cache_key] = list(
                view_type.field_options_model_class.objects_and_trash.filter(
                    **{
                        view_type.model_reference_field_name: view,
                        "field__table_id": view.table_id,
                    }
                )
            )

        return {
            "field_options": {
                field_options.field_id: {
                    self.field_option_key: getattr(field_options, self.field_option_key)
                }
                for field_options in cache[cache_key]
            }
        }

    def apply_configuration(
        self,
        view: View,
        configuration: Dict[str, Any],
        user: Optional[AbstractUser] = None,
        preserve_ids: bool = False,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[FieldOptionsDict]:
        return {
            int(field_id): values
            for field_id, values in configuration["field_options"].items()
        }


class FieldVisibilityViewConfigurationCopyCategoryType(FieldOptionsCopyCategoryType):
    type = "field_visibility"
    field_option_key = "hidden"


class FieldOrderViewConfigurationCopyCategoryType(FieldOptionsCopyCategoryType):
    type = "field_order"
    field_option_key = "order"


class FieldWidthsViewConfigurationCopyCategoryType(FieldOptionsCopyCategoryType):
    type = "field_widths"
    field_option_key = "width"


class ViewSettingsViewConfigurationCopyCategoryType(ViewConfigurationCopyCategoryType):
    """
    Copies the plain view attributes that a view type declares in
    `ViewType.copyable_view_attributes`, the row height and frozen column count of a
    grid view for example. Only the attributes that both the source and the
    destination view type declare are copied, so cross view type copies stay safe.
    """

    type = "view_settings"
    operation_types = [UpdateViewOperationType]

    def is_supported(self, view_type: ViewType) -> bool:
        return len(view_type.copyable_view_attributes) > 0

    def export_configuration(
        self, view: View, cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        view_type = view_type_registry.get_by_model(view.specific_class)
        return {
            "view_attributes": {
                attribute: getattr(view, attribute)
                for attribute in view_type.copyable_view_attributes
            }
        }

    def apply_configuration(
        self,
        view: View,
        configuration: Dict[str, Any],
        user: Optional[AbstractUser] = None,
        preserve_ids: bool = False,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[FieldOptionsDict]:
        view_type = view_type_registry.get_by_model(view.specific_class)
        applied_attributes = [
            attribute
            for attribute in configuration["view_attributes"]
            if attribute in view_type.copyable_view_attributes
        ]
        for attribute in applied_attributes:
            setattr(view, attribute, configuration["view_attributes"][attribute])
        if applied_attributes:
            view.save(update_fields=applied_attributes)
        return None


class FiltersViewConfigurationCopyCategoryType(ViewConfigurationCopyCategoryType):
    type = "filters"
    # The delete operations are deliberately absent because they take the
    # filter itself as context instead of the view, and the create operation
    # is the gate the ownership managers hide the configuration behind.
    operation_types = [
        CreateViewFilterOperationType,
        CreateViewFilterGroupOperationType,
        # For the `filter_type` and `filters_disabled` view attributes.
        UpdateViewOperationType,
    ]

    def is_supported(self, view_type: ViewType) -> bool:
        return view_type.can_filter

    def export_configuration(
        self, view: View, cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "filter_type": view.filter_type,
            "filters_disabled": view.filters_disabled,
            "filter_groups": [
                {
                    "id": filter_group.id,
                    "filter_type": filter_group.filter_type,
                    "parent_group_id": filter_group.parent_group_id,
                }
                for filter_group in view.filter_groups.all().order_by("id")
            ],
            "filters": [
                {
                    "id": view_filter.id,
                    "field_id": view_filter.field_id,
                    "type": view_filter.type,
                    "value": view_filter.value,
                    "group_id": view_filter.group_id,
                }
                for view_filter in _including_trashed_fields(ViewFilter, view).order_by(
                    "id"
                )
            ],
        }

    def apply_configuration(
        self,
        view: View,
        configuration: Dict[str, Any],
        user: Optional[AbstractUser] = None,
        preserve_ids: bool = False,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[FieldOptionsDict]:
        _including_trashed_fields(ViewFilter, view).delete()
        view.filter_groups.all().delete()

        view.filter_type = configuration["filter_type"]
        view.filters_disabled = configuration["filters_disabled"]
        view.save(update_fields=["filter_type", "filters_disabled"])

        # Nested filter groups always have a higher id than their parent, so creating
        # them sorted by id guarantees that a parent's new id is already in the
        # mapping when a child references it.
        group_id_mapping = {}
        for group in sorted(
            configuration["filter_groups"], key=lambda group: group["id"]
        ):
            created_group = ViewFilterGroup.objects.create(
                id=group["id"] if preserve_ids else None,
                view=view,
                filter_type=group["filter_type"],
                parent_group_id=group_id_mapping.get(group["parent_group_id"]),
            )
            group_id_mapping[group["id"]] = created_group.id

        existing_field_ids = _existing_field_ids(view, cache)
        ViewFilter.objects.bulk_create(
            [
                ViewFilter(
                    id=view_filter["id"] if preserve_ids else None,
                    view=view,
                    field_id=view_filter["field_id"],
                    type=view_filter["type"],
                    value=view_filter["value"],
                    group_id=group_id_mapping.get(view_filter["group_id"]),
                )
                for view_filter in configuration["filters"]
                if view_filter["field_id"] in existing_field_ids
            ]
        )
        return None

    def after_applied(self, view: View):
        # Changed filters invalidate the view's aggregations, for example.
        view_type_registry.get_by_model(view.specific_class).after_filter_update(view)


class SortsViewConfigurationCopyCategoryType(ViewConfigurationCopyCategoryType):
    type = "sorts"
    operation_types = [CreateViewSortOperationType]

    def is_supported(self, view_type: ViewType) -> bool:
        return view_type.can_sort

    def export_configuration(
        self, view: View, cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "sorts": [
                {
                    "id": view_sort.id,
                    "field_id": view_sort.field_id,
                    "order": view_sort.order,
                    "type": view_sort.type,
                    "priority": view_sort.priority,
                }
                for view_sort in _including_trashed_fields(ViewSort, view)
            ]
        }

    def apply_configuration(
        self,
        view: View,
        configuration: Dict[str, Any],
        user: Optional[AbstractUser] = None,
        preserve_ids: bool = False,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[FieldOptionsDict]:
        _including_trashed_fields(ViewSort, view).delete()
        existing_field_ids = _existing_field_ids(view, cache)
        ViewSort.objects.bulk_create(
            [
                ViewSort(
                    id=view_sort["id"] if preserve_ids else None,
                    view=view,
                    field_id=view_sort["field_id"],
                    order=view_sort["order"],
                    type=view_sort["type"],
                    priority=view_sort["priority"],
                )
                for view_sort in configuration["sorts"]
                if view_sort["field_id"] in existing_field_ids
            ]
        )
        return None


class GroupBysViewConfigurationCopyCategoryType(ViewConfigurationCopyCategoryType):
    type = "group_bys"
    operation_types = [CreateViewGroupByOperationType]

    def is_supported(self, view_type: ViewType) -> bool:
        return view_type.can_group_by

    def export_configuration(
        self, view: View, cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "group_bys": [
                {
                    "id": view_group_by.id,
                    "field_id": view_group_by.field_id,
                    "order": view_group_by.order,
                    "type": view_group_by.type,
                    "width": view_group_by.width,
                    "priority": view_group_by.priority,
                }
                for view_group_by in _including_trashed_fields(ViewGroupBy, view)
            ]
        }

    def apply_configuration(
        self,
        view: View,
        configuration: Dict[str, Any],
        user: Optional[AbstractUser] = None,
        preserve_ids: bool = False,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[FieldOptionsDict]:
        _including_trashed_fields(ViewGroupBy, view).delete()
        existing_field_ids = _existing_field_ids(view, cache)
        ViewGroupBy.objects.bulk_create(
            [
                ViewGroupBy(
                    id=view_group_by["id"] if preserve_ids else None,
                    view=view,
                    field_id=view_group_by["field_id"],
                    order=view_group_by["order"],
                    type=view_group_by["type"],
                    width=view_group_by["width"],
                    priority=view_group_by["priority"],
                )
                for view_group_by in configuration["group_bys"]
                if view_group_by["field_id"] in existing_field_ids
            ]
        )
        return None


class DefaultRowValuesViewConfigurationCopyCategoryType(
    ViewConfigurationCopyCategoryType
):
    type = "default_row_values"
    operation_types = [
        ReadViewDefaultValuesOperationType,
        UpdateViewDefaultValuesOperationType,
    ]

    def is_supported(self, view_type: ViewType) -> bool:
        return view_type.can_set_default_values

    def export_configuration(
        self, view: View, cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "default_row_values": [
                {
                    "id": default_value.id,
                    "field_id": default_value.field_id,
                    "enabled": default_value.enabled,
                    "value": default_value.value,
                    "field_type": default_value.field_type,
                    "function": default_value.function,
                }
                for default_value in view.view_default_values.all()
            ]
        }

    def apply_configuration(
        self,
        view: View,
        configuration: Dict[str, Any],
        user: Optional[AbstractUser] = None,
        preserve_ids: bool = False,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[FieldOptionsDict]:
        view.view_default_values.all().delete()
        existing_field_ids = _existing_field_ids(view, cache)
        ViewDefaultValue.objects.bulk_create(
            [
                ViewDefaultValue(
                    id=default_value["id"] if preserve_ids else None,
                    view=view,
                    field_id=default_value["field_id"],
                    enabled=default_value["enabled"],
                    value=default_value["value"],
                    field_type=default_value["field_type"],
                    function=default_value["function"],
                )
                for default_value in configuration["default_row_values"]
                if default_value["field_id"] in existing_field_ids
            ]
        )
        return None


class DecorationsViewConfigurationCopyCategoryType(ViewConfigurationCopyCategoryType):
    type = "decorations"
    operation_types = [CreateViewDecorationOperationType]

    def is_supported(self, view_type: ViewType) -> bool:
        return view_type.can_decorate

    def export_configuration(
        self, view: View, cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "decorations": [
                {
                    "id": decoration.id,
                    "type": decoration.type,
                    "value_provider_type": decoration.value_provider_type,
                    "value_provider_conf": decoration.value_provider_conf,
                    "order": decoration.order,
                }
                for decoration in view.viewdecoration_set.all()
            ]
        }

    def apply_configuration(
        self,
        view: View,
        configuration: Dict[str, Any],
        user: Optional[AbstractUser] = None,
        preserve_ids: bool = False,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[FieldOptionsDict]:
        # The decorator and value provider types can enforce constraints, a
        # premium license for example, so their hooks must still be called even
        # though the decorations are bulk created. Types that are not
        # registered, because the app providing them has been removed for
        # example, are copied without the hook, like `duplicate_view` does.
        decorator_type_names = {
            decoration["type"] for decoration in configuration["decorations"]
        }
        for decorator_type_name in decorator_type_names:
            try:
                decorator_type = decorator_type_registry.get(decorator_type_name)
            except DecoratorTypeDoesNotExist:
                continue
            decorator_type.before_create_decoration(view, user)
        value_provider_type_names = {
            decoration["value_provider_type"]
            for decoration in configuration["decorations"]
            if decoration["value_provider_type"]
        }
        for value_provider_type_name in value_provider_type_names:
            try:
                value_provider_type = decorator_value_provider_type_registry.get(
                    value_provider_type_name
                )
            except DecoratorValueProviderTypeDoesNotExist:
                continue
            value_provider_type.before_create_decoration(view, user)

        view.viewdecoration_set.all().delete()
        ViewDecoration.objects.bulk_create(
            [
                ViewDecoration(
                    id=decoration["id"] if preserve_ids else None,
                    view=view,
                    type=decoration["type"],
                    value_provider_type=decoration["value_provider_type"],
                    value_provider_conf=decoration["value_provider_conf"],
                    order=decoration["order"],
                )
                for decoration in configuration["decorations"]
            ]
        )
        return None
