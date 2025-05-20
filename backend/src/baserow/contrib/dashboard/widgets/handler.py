from typing import Iterable, cast

from django.core.files.storage import Storage
from django.db.models import QuerySet

from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.types import WidgetDict
from baserow.contrib.dashboard.widgets.registries import (
    WidgetType,
    widget_type_registry,
)
from baserow.core.db import specific_iterator
from baserow.core.storage import ExportZipFile
from baserow.core.utils import extract_allowed

from .exceptions import WidgetDoesNotExist
from .models import Widget
from .types import UpdatedWidget, WidgetForUpdate


class WidgetHandler:
    def get_widget(
        self, widget_id: int, base_queryset: QuerySet | None = None
    ) -> Widget:
        """
        Returns a widget instance from the database.

        :param widget_id: The Id of the widget.
        :param base_queryset: The base queryset to use to build the query.
        :raises WidgetDoesNotExist: If the widget can't be found.
        :return: The widget instance.
        """

        queryset = base_queryset if base_queryset is not None else Widget.objects.all()

        try:
            widget = queryset.select_related("dashboard", "dashboard__workspace").get(
                id=widget_id
            )
            specific_widget: Widget = widget.specific
            specific_widget.dashboard = widget.dashboard
        except Widget.DoesNotExist:
            raise WidgetDoesNotExist()

        return specific_widget

    def get_widget_for_update(
        self, widget_id: int, base_queryset: QuerySet | None = None
    ) -> WidgetForUpdate:
        """
        Returns a widget instance from the database that can be safely updated.

        :param widget_id: The Id of the widget.
        :param base_queryset: The base queryset to use to build the query.
        :raises WidgetDoesNotExist: If the widget can't be found.
        :return: The widget instance.
        """

        queryset = base_queryset if base_queryset is not None else Widget.objects.all()

        queryset = queryset.select_related(
            "dashboard", "dashboard__workspace"
        ).select_for_update(of=("self",))

        return cast(
            WidgetForUpdate,
            self.get_widget(
                widget_id,
                base_queryset=queryset,
            ),
        )

    def get_widgets(
        self,
        dashboard: Dashboard,
        base_queryset: QuerySet | None = None,
        specific: bool = True,
    ) -> QuerySet[Widget] | Iterable[Widget]:
        """
        Gets all the specific widgets of a given page.

        :param dashboard: The dashboard that holds the widgets.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Whether to return the generic widgets or the specific
            instances.
        :return: The widgets of the dashboard.
        """

        queryset = base_queryset if base_queryset is not None else Widget.objects.all()
        queryset = queryset.select_related("dashboard", "dashboard__workspace").filter(
            dashboard=dashboard
        )

        if specific:
            queryset = queryset.select_related("content_type")
            widgets = specific_iterator(
                queryset,
                per_content_type_queryset_hook=(
                    lambda widget, queryset: widget_type_registry.get_by_model(
                        widget
                    ).enhance_queryset(queryset)
                ),
            )
        else:
            widgets = queryset

        return widgets

    def create_widget(
        self,
        widget_type: WidgetType,
        dashboard: Dashboard,
        **kwargs,
    ) -> Widget:
        """
        Creates a new widget in a dashboard.

        :param widget_type: The type of the widget.
        :param dashboard: The dashboard the widget should be put in.
        :param kwargs: Additional attributes of the widget.
        :return: The created widget.
        """

        order = Widget.get_last_order(dashboard)
        allowed_values = extract_allowed(kwargs, widget_type.allowed_fields)

        allowed_values["dashboard"] = dashboard
        allowed_values = widget_type.prepare_value_for_db(allowed_values)

        model_class = cast(Widget, widget_type.model_class)
        widget = model_class(order=order, **allowed_values)
        widget._ensure_content_type_is_set()
        widget.full_clean()
        widget.save()

        return widget

    def update_widget(self, widget: WidgetForUpdate, **kwargs) -> UpdatedWidget:
        """
        Updates a widget with values if the values are allowed
        to be set on the widget.

        :param widget: The widget that should be updated.
        :param kwargs: The values that should be set on the widget.
        :return: The updated widget.
        """

        allowed_values = extract_allowed(kwargs, widget.get_type().allowed_fields)

        original_widget_values = widget.get_type().export_prepared_values(
            instance=widget
        )

        for key, value in allowed_values.items():
            setattr(widget, key, value)

        widget.full_clean()
        widget.save()

        new_widget_values = widget.get_type().export_prepared_values(instance=widget)

        return UpdatedWidget(widget, original_widget_values, new_widget_values)

    def delete_widget(self, widget: Widget):
        """
        Deletes the provided widget.

        :param widget: Widget to delete.
        """

        widget_type = widget_type_registry.get_by_model(widget)
        widget.delete()
        widget_type.after_delete(widget)

    def export_widget(
        self,
        widget: Widget,
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        cache: dict[str, any] | None = None,
    ) -> WidgetDict:
        """
        Serializes the given widget.

        :param widget: The instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Optional storage to use.
        :param cache: Optional cache to use.
        :return: The serialized version.
        """

        widget_type = widget_type_registry.get_by_model(widget)

        return cast(
            WidgetDict,
            widget_type.export_serialized(
                widget, files_zip=files_zip, storage=storage, cache=cache
            ),
        )

    def import_widget(
        self,
        dashboard: Dashboard,
        serialized_widget: WidgetDict,
        id_mapping: dict[str, dict[int, int]],
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        cache: dict[str, any] | None = None,
    ) -> Widget:
        """
        Creates a widget instance from its serialized form.

        :param dashboard: The dashboard instance the new widget should belong to.
        :param serialized_widget: The serialized version of the widget.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :return: the new widget instance.
        """

        widget_type = widget_type_registry.get(serialized_widget["type"])
        widget = widget_type.import_serialized(
            dashboard,
            serialized_widget,
            id_mapping,
            files_zip,
            storage,
            cache,
        )
        return widget
