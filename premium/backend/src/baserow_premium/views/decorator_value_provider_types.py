from typing import Any, Callable, Dict, Optional, Set, Tuple
from uuid import uuid4

from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.fields.field_types import SingleSelectFieldType
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewDecoration
from baserow.contrib.database.views.registries import (
    DecoratorValueProviderType,
    view_filter_type_registry,
)

from ..license.features import PREMIUM
from .decorator_types import BackgroundColorDecoratorType, LeftBorderColorDecoratorType
from .serializers import (
    ConditionalColorValueProviderConfColorsSerializer,
    SelectColorValueProviderConfSerializer,
)


class PremiumDecoratorValueProviderType(DecoratorValueProviderType):
    def before_create_decoration(self, view, user):
        if user:
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user, view.table.database.workspace
            )

    def before_update_decoration(self, view_decoration, user):
        if user:
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user, view_decoration.view.table.database.workspace
            )


class SelectColorValueProviderType(PremiumDecoratorValueProviderType):
    type = "single_select_color"

    compatible_decorator_types = [
        LeftBorderColorDecoratorType.type,
        BackgroundColorDecoratorType.type,
    ]

    value_provider_conf_serializer_class = SelectColorValueProviderConfSerializer

    def set_import_serialized_value(
        self, value: Dict[str, Any], id_mapping: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update the field id with the newly created one.
        """

        old_field_id = value["value_provider_conf"].get("field_id", None)

        if old_field_id:
            value["value_provider_conf"]["field_id"] = id_mapping[
                "database_fields"
            ].get(old_field_id, None)

        return value

    def after_field_delete(self, deleted_field):
        """
        Remove the field from the value_provider_conf filters if necessary.
        """

        view_handler = ViewHandler()

        queryset = ViewDecoration.objects.filter(
            view__table=deleted_field.table,
            value_provider_type=SelectColorValueProviderType.type,
            value_provider_conf__field_id=deleted_field.id,
        )

        for decoration in queryset.all():
            new_conf = {**decoration.value_provider_conf}
            new_conf["field_id"] = None
            view_handler.update_decoration(decoration, value_provider_conf=new_conf)

    def after_field_type_change(self, field):
        """
        Unset the field if the type is not a select anymore.
        """

        from baserow.contrib.database.fields.registries import field_type_registry

        field_type = field_type_registry.get_by_model(field.specific_class)

        view_handler = ViewHandler()

        if field_type.type != SingleSelectFieldType.type:
            queryset = ViewDecoration.objects.filter(
                view__table=field.table,
                value_provider_type=SelectColorValueProviderType.type,
                value_provider_conf__field_id=field.id,
            )

            for decoration in queryset.all():
                new_conf = {**decoration.value_provider_conf}
                new_conf["field_id"] = None
                view_handler.update_decoration(decoration, value_provider_conf=new_conf)


class ConditionalColorValueProviderType(PremiumDecoratorValueProviderType):
    type = "conditional_color"

    compatible_decorator_types = [
        LeftBorderColorDecoratorType.type,
        BackgroundColorDecoratorType.type,
    ]

    value_provider_conf_serializer_class = (
        ConditionalColorValueProviderConfColorsSerializer
    )

    def set_import_serialized_value(
        self, value: Dict[str, Any], id_mapping: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update the field ids of each filter with the newly created one.
        """

        value_provider_conf = value["value_provider_conf"]

        for color in value_provider_conf["colors"]:
            # templates can have colors without an id, but we need one to be able to
            # correctly update the color later on in the frontend.
            if "id" not in color:
                color["id"] = str(uuid4())

            for color_filter in color["filters"]:
                new_value = (
                    id_mapping["database_field_select_options"].get(
                        int(color_filter["value"])
                    )
                    if "database_field_select_options" in id_mapping
                    and str(color_filter["value"]).isdigit()
                    else color_filter["value"]
                )
                color_filter["value"] = new_value
                new_field_id = id_mapping["database_fields"][color_filter["field"]]
                color_filter["field"] = new_field_id

        return value

    def _map_filter_from_config(
        self,
        conf: Dict[str, Any],
        fn: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Map a function on each filter of the configuration. If the given
        function returns None, the filter will be removed from the filter list.
        This method is useful to remove filters from the configuration matching
        a particular condition checked in the provided function (i.e. remove all
        the filters related to a deleted field). It also updates the list of
        filter groups for every color, removing any groups that are no longer
        referenced. Please, note that this function will modify the given
        configuration in place.

        :param conf: The conditional color configuration to process.
        :param fn: The function to apply to each filter.
        :return: A tuple of the modified configuration and a boolean value
            indicating if at least one filter was removed.
        """

        modified = False

        for color in conf["colors"]:
            modified_filters, found_group_ids = self._process_filters(color, fn)
            modified = modified or modified_filters

            filter_groups = color.get("filter_groups", None)
            if filter_groups:
                color["filter_groups"] = [
                    group for group in filter_groups if group["id"] in found_group_ids
                ]

        return conf, modified

    def _process_filters(
        self,
        color: Dict[str, Any],
        fn: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
    ) -> Tuple[bool, Set[int]]:
        """
        Process each filter in the color configuration. Returns a tuple of
        modified status and filter group IDs referenced by filters. The value of
        modified will be True if at least one filter was removed. The value of
        found_group_ids will be a set of group IDs that were referenced by
        filters that were not removed.

        :param color: The color configuration to process.
        :param fn: The function to apply to each filter.
        :return: A tuple of modified status and a set of filter group IDs
            referenced by the remaining filters.
        """

        new_filters = []
        found_group_ids = set()

        for filter in color["filters"]:
            new_filter = fn(filter)

            if new_filter is None:
                continue

            new_filters.append(new_filter)
            group_id = new_filter.get("group")

            if group_id:
                found_group_ids.add(group_id)

        modified = len(new_filters) != len(color["filters"])
        color["filters"] = new_filters

        return modified, found_group_ids

    def after_field_delete(self, deleted_field):
        """
        Remove the field from the value_provider_conf filters if necessary.
        """

        # We can't filter with the JSON field here as we have nested lists
        queryset = ViewDecoration.objects.filter(
            view__table=deleted_field.table,
            value_provider_type=ConditionalColorValueProviderType.type,
        )

        view_handler = ViewHandler()

        for decoration in queryset.all():
            new_conf, modified = self._map_filter_from_config(
                decoration.value_provider_conf,
                lambda f: None if f["field"] == deleted_field.id else f,
            )
            if modified:
                view_handler.update_decoration(decoration, value_provider_conf=new_conf)

    def after_field_type_change(self, field):
        """
        Remove filters type that are not compatible anymore from configuration
        """

        queryset = ViewDecoration.objects.filter(
            view__table=field.table,
            value_provider_type=ConditionalColorValueProviderType.type,
        )

        view_handler = ViewHandler()

        def compatible_filter_only(filter):
            if filter["field"] != field.id:
                return filter

            filter_type = view_filter_type_registry.get(filter["type"])
            if not filter_type.field_is_compatible(field):
                return None
            return filter

        for decoration in queryset.all():
            # Check which filters are not compatible anymore and remove those.
            new_conf, modified = self._map_filter_from_config(
                decoration.value_provider_conf,
                compatible_filter_only,
            )

            if modified:
                view_handler.update_decoration(decoration, value_provider_conf=new_conf)
