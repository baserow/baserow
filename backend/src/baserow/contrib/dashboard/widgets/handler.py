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
from baserow.core.telemetry.utils import baserow_trace_handler
from baserow.core.utils import extract_allowed

from .exceptions import WidgetDoesNotExist
from .models import Widget
from .types import UpdatedWidget, WidgetForUpdate


@baserow_trace_handler
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

    def get_widgets_for_update(self, dashboard: Dashboard) -> list[Widget]:
        """Returns all active dashboard widgets locked for a layout mutation."""

        return list(
            Widget.objects.select_related(
                "dashboard", "dashboard__workspace", "content_type"
            )
            .filter(dashboard=dashboard)
            .select_for_update(of=("self",))
            .order_by("id")
        )

    @staticmethod
    def get_widget_layout(widget: Widget) -> dict[str, int]:
        return {
            "id": widget.id,
            "grid_x": widget.grid_x,
            "grid_y": widget.grid_y,
            "grid_width": widget.grid_width,
            "grid_height": widget.grid_height,
        }

    @staticmethod
    def _layouts_overlap(first: dict[str, int], second: dict[str, int]) -> bool:
        return (
            first["grid_x"] < second["grid_x"] + second["grid_width"]
            and second["grid_x"] < first["grid_x"] + first["grid_width"]
            and first["grid_y"] < second["grid_y"] + second["grid_height"]
            and second["grid_y"] < first["grid_y"] + first["grid_height"]
        )

    def get_compacted_widget_layout(
        self, widgets: Iterable[Widget]
    ) -> list[dict[str, int]]:
        """Returns a deterministic vertically compacted layout.

        Widgets retain their horizontal position and dimensions. They are processed
        top-to-bottom, then left-to-right, so a deletion produces the same result on
        every client without relying on the browser grid implementation.
        """

        compacted_layout = []
        for widget in sorted(
            widgets,
            key=lambda widget: (widget.grid_y, widget.grid_x, widget.id),
        ):
            layout = self.get_widget_layout(widget)
            layout["grid_y"] = 0

            while any(
                self._layouts_overlap(layout, other) for other in compacted_layout
            ):
                layout["grid_y"] += 1

            compacted_layout.append(layout)

        return compacted_layout

    def get_last_grid_y(self, dashboard: Dashboard) -> int:
        """Returns the first free row after every active widget in a dashboard."""

        return max(
            (
                grid_y + grid_height
                for grid_y, grid_height in Widget.objects.filter(
                    dashboard=dashboard
                ).values_list("grid_y", "grid_height")
            ),
            default=0,
        )

    def place_restored_widget_at_bottom(self, widget: Widget) -> None:
        """Places a restored widget after the active dashboard layout.

        A widget can have been deleted while the remaining layout compacted. Restoring
        it at its old coordinates could therefore overlap an active widget. Generic
        trash restores preserve the current dashboard and append the widget instead;
        undo actions subsequently restore their recorded complete layout.
        """

        grid_y = max(
            (
                other_grid_y + other_grid_height
                for other_grid_y, other_grid_height in Widget.objects.filter(
                    dashboard=widget.dashboard
                )
                .exclude(id=widget.id)
                .values_list("grid_y", "grid_height")
            ),
            default=0,
        )
        widget.grid_y = grid_y
        widget.save(update_fields=["grid_y", "updated_on"])

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
        grid_layout = widget_type.get_grid_layout()

        allowed_values["dashboard"] = dashboard
        allowed_values = widget_type.prepare_value_for_db(allowed_values)

        model_class = cast(Widget, widget_type.model_class)
        widget = model_class(
            order=order,
            grid_x=0,
            grid_y=self.get_last_grid_y(dashboard),
            grid_width=grid_layout.default_width,
            grid_height=grid_layout.default_height,
            **allowed_values,
        )
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

    def update_widget_layout(
        self,
        widgets: list[Widget],
        layout_by_widget_id: dict[int, dict[str, int]],
    ) -> None:
        """Persists an already validated complete dashboard layout."""

        for widget in widgets:
            layout = layout_by_widget_id[widget.id]
            widget.grid_x = layout["grid_x"]
            widget.grid_y = layout["grid_y"]
            widget.grid_width = layout["grid_width"]
            widget.grid_height = layout["grid_height"]
            widget.save(
                update_fields=[
                    "grid_x",
                    "grid_y",
                    "grid_width",
                    "grid_height",
                    "updated_on",
                ]
            )

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
        grid_fields = ("grid_x", "grid_y", "grid_width", "grid_height")

        # Exports created before the grid layout was introduced do not carry
        # geometry. Place those widgets one below another using the defaults of
        # their type, instead of relying on the model defaults and overlapping
        # every imported widget at (0, 0).
        if not all(field in serialized_widget for field in grid_fields):
            grid_layout = widget_type.get_grid_layout()
            serialized_widget = {
                **serialized_widget,
                "grid_x": 0,
                "grid_y": self.get_last_grid_y(dashboard),
                "grid_width": grid_layout.default_width,
                "grid_height": grid_layout.default_height,
            }

        widget = widget_type.import_serialized(
            dashboard,
            serialized_widget,
            id_mapping,
            files_zip,
            storage,
            cache,
        )
        return widget
