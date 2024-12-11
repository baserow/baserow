from abc import ABC
from typing import Type

from baserow.contrib.dashboard.types import WidgetDict
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

    SerializedDict = Type[WidgetDict]
    parent_property_name = "dashboard"
    id_mapping_name = DASHBOARD_WIDGETS
    allowed_fields = ["title", "description"]

    def prepare_value_for_db(self, values: dict, instance: Widget | None = None):
        """
        This function allows you to hook into the moment a widget is created or
        updated. If the widget is updated, `instance` of the current widget
        will be defined.

        :param values: The values that are being updated
        :param instance: (optional) The existing instance that is being updated
        """

        return values

    def after_delete(self, instance: Widget):
        """
        This function allows you to hook into the moment after a widget is
        deleted.

        :param instance: The instance that was deleted.
        """

        pass


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
