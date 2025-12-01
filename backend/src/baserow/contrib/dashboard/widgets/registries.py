from abc import ABC
from decimal import Decimal

from django.db.models import QuerySet

from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.types import WidgetDict
from baserow.contrib.dashboard.widgets.types import UpdatedWidget
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    EasyImportExportMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)

from .exceptions import WidgetTypeDoesNotExist
from .models import Widget

DASHBOARD_WIDGETS = "dashboard_widgets"


class WidgetType(
    EasyImportExportMixin[Widget],
    CustomFieldsInstanceMixin,
    ModelInstanceMixin[Widget],
    Instance,
    ABC,
):
    """Widget type"""

    SerializedDict = WidgetDict
    parent_property_name = "dashboard"
    id_mapping_name = DASHBOARD_WIDGETS
    allowed_fields = ["title", "description"]

    def enhance_queryset(self, queryset: QuerySet[Widget]) -> QuerySet[Widget]:
        """
        Enhances the queryset to fetch data in a more efficient way.

        :param queryset: The queryset that lists the widgets.
        :return: The same queryset with proper select_related and/or prefetch_related to
            reduce the number of queries necessary to fetch the data.
        """

        return queryset

    def before_create(self, user, dashboard: Dashboard):
        """
        This function allows you to perform checks and operations
        before a widget is created.

        :param user: The user on whos behalf the widget is being
            created.
        :param dashboard: The dashboard where the widget should be
            created.
        """

        pass

    def after_update(self, updated_widget: UpdatedWidget, **kwargs) -> UpdatedWidget:
        """
        Method to do any post-update actions based on the widget type.

        :param updated_widget: The updated widget instance.
        :param kwargs: The original values passed for update.
        :return instance: The original or modified updated widget instance.
        """

        return updated_widget

    def prepare_value_for_db(self, values: dict, instance: Widget | None = None):
        """
        This function allows you to hook into the moment a widget is created or
        updated. If the widget is updated, `instance` of the current widget
        will be defined.

        :param values: The values that are being updated
        :param instance: (optional) The existing instance that is being updated
        """

        return values

    def export_prepared_values(self, instance: Widget):
        """
        Returns a serializable dict of prepared values for the widget attributes.
        It is called by undo/redo ActionHandler to store the values in a way that
        could be restored later.

        :param instance: The widget instance to export values for.
        :return: A dict of prepared values.
        """

        values = {key: getattr(instance, key) for key in self.allowed_fields}
        return values

    def after_delete(self, instance: Widget):
        """
        This function allows you to hook into the moment after a widget is
        deleted.

        :param instance: The instance that was deleted.
        """

        pass

    def before_trashed(self, instance: Widget):
        """
        This function allows you to hook into the process of trashing
        a widget and do widget type specific steps.

        :param instance: The instance that will be restored.
        """

        pass

    def before_restore(self, instance: Widget):
        """
        This function allows you to hook into the process of restoring
        a widget and do widget type specific steps.

        :param instance: The instance that will be restored.
        """

        pass

    def deserialize_property(
        self,
        prop_name: str,
        value: any,
        id_mapping: dict[str, any],
        **kwargs,
    ) -> any:
        if prop_name == "order" and value:
            return Decimal(value)

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            **kwargs,
        )

    def serialize_property(
        self,
        instance: Widget,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "order":
            return str(instance.order)

        return super().serialize_property(
            instance,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )


class WidgetTypeRegistry(
    Registry[WidgetType],
    ModelRegistryMixin[Widget, WidgetType],
    CustomFieldsRegistryMixin,
):
    """
    Contains all registered widget types.
    """

    name = "dashboard_widget"
    does_not_exist_exception_class = WidgetTypeDoesNotExist


widget_type_registry = WidgetTypeRegistry()
