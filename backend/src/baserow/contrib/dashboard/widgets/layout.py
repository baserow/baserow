"""Canonical validation and transformation of dashboard widget layouts."""

from collections.abc import Iterable

from django.utils import timezone

from .exceptions import WidgetLayoutInvalid
from .grid_layout import (
    compact_widget_layout,
    fits_within_grid_columns,
    layouts_overlap,
)
from .models import Widget
from .types import WidgetLayoutDelta, WidgetLayoutDict


class WidgetLayoutHandler:
    """Validates, canonicalizes, and persists one locked widget layout.

    Callers give this handler the authoritative widget rows locked by the service. It
    deliberately has no permission or signalling concerns: its complete contract is
    turning layouts into a validated delta and writing only the rows in that delta.
    """

    def __init__(self, widgets: Iterable[Widget]):
        self.widgets = sorted(widgets, key=lambda widget: widget.id)

    @staticmethod
    def from_widget(widget: Widget) -> WidgetLayoutDict:
        return {
            "id": widget.id,
            "grid_x": widget.grid_x,
            "grid_y": widget.grid_y,
            "grid_width": widget.grid_width,
            "grid_height": widget.grid_height,
        }

    @property
    def current_layout(self) -> list[WidgetLayoutDict]:
        return [self.from_widget(widget) for widget in self.widgets]

    @property
    def compacted_layout(self) -> list[WidgetLayoutDict]:
        """Returns the canonical vertical compaction of the locked layout."""

        return compact_widget_layout(self.current_layout)

    def validate(
        self,
        layout: list[WidgetLayoutDict],
        *,
        enforce_vertical_bound: bool = True,
        compact: bool = False,
        fixed_layouts: Iterable[WidgetLayoutDict] = (),
        existing_grid_bottom: int = 0,
    ) -> dict[int, WidgetLayoutDict]:
        """Validates and optionally compacts one complete widget layout.

        ``existing_grid_bottom`` allows a pre-existing rollout-era gap to remain
        addressable without letting a request expand the layout beyond its current
        extent. The sum of movable and fixed widget heights remains the normal
        defensive bound.
        """

        fixed_layout = list(fixed_layouts)

        if len(layout) != len(self.widgets):
            raise WidgetLayoutInvalid("The layout must include every dashboard widget.")

        layout_by_widget_id: dict[int, WidgetLayoutDict] = {}
        for item in layout:
            try:
                widget_id = item["id"]
                grid_x = item["grid_x"]
                grid_y = item["grid_y"]
                grid_width = item["grid_width"]
                grid_height = item["grid_height"]
            except (KeyError, TypeError) as exc:
                raise WidgetLayoutInvalid("The layout item is incomplete.") from exc

            values = (widget_id, grid_x, grid_y, grid_width, grid_height)
            if any(type(value) is not int for value in values):
                raise WidgetLayoutInvalid("The layout values must be integers.")
            if widget_id in layout_by_widget_id:
                raise WidgetLayoutInvalid("A widget can only occur once in the layout.")
            if grid_x < 0 or grid_y < 0 or grid_width < 1 or grid_height < 1:
                raise WidgetLayoutInvalid(
                    "The layout contains an invalid grid position."
                )

            layout_by_widget_id[widget_id] = {
                "id": widget_id,
                "grid_x": grid_x,
                "grid_y": grid_y,
                "grid_width": grid_width,
                "grid_height": grid_height,
            }

        if set(layout_by_widget_id) != {widget.id for widget in self.widgets}:
            raise WidgetLayoutInvalid(
                "The layout widgets do not match the dashboard widgets."
            )

        normalized_layout = []
        for widget in self.widgets:
            item = layout_by_widget_id[widget.id]
            constraints = widget.get_type().get_grid_layout()
            if not fits_within_grid_columns(item):
                raise WidgetLayoutInvalid(
                    "A widget cannot extend past the sixth column."
                )
            if not constraints.min_width <= item["grid_width"] <= constraints.max_width:
                raise WidgetLayoutInvalid("The widget width is outside of its limits.")
            if not (
                constraints.min_height <= item["grid_height"] <= constraints.max_height
            ):
                raise WidgetLayoutInvalid("The widget height is outside of its limits.")
            normalized_layout.append(item)

        for index, item in enumerate(normalized_layout):
            for other in normalized_layout[index + 1 :]:
                if layouts_overlap(item, other):
                    raise WidgetLayoutInvalid("Dashboard widgets cannot overlap.")

        if enforce_vertical_bound:
            total_grid_height = sum(
                item["grid_height"] for item in [*normalized_layout, *fixed_layout]
            )
            height_growth = sum(
                max(0, item["grid_height"] - widget.grid_height)
                for widget, item in zip(self.widgets, normalized_layout, strict=True)
            )
            max_grid_bottom = max(
                total_grid_height,
                existing_grid_bottom + height_growth,
            )
            if any(
                item["grid_y"] + item["grid_height"] > max_grid_bottom
                for item in normalized_layout
            ):
                raise WidgetLayoutInvalid(
                    "A widget cannot be positioned below the total layout height."
                )

        if compact:
            normalized_layout = compact_widget_layout(
                normalized_layout,
                fixed_layouts=fixed_layout,
            )

        return {item["id"]: item for item in normalized_layout}

    def merge_delta(
        self,
        layout_delta: list[WidgetLayoutDict],
        *,
        enforce_vertical_bound: bool = True,
    ) -> tuple[list[WidgetLayoutDict], dict[int, WidgetLayoutDict]]:
        """Merges recorded geometries into the current locked layout."""

        current_layout = self.current_layout
        current_by_id = {item["id"]: item for item in current_layout}
        delta_by_id: dict[int, WidgetLayoutDict] = {}
        for item in layout_delta:
            try:
                widget_id = item["id"]
            except (KeyError, TypeError) as exc:
                raise WidgetLayoutInvalid("The layout item is incomplete.") from exc
            if type(widget_id) is not int or widget_id in delta_by_id:
                raise WidgetLayoutInvalid("A widget can only occur once in the layout.")
            if widget_id not in current_by_id:
                raise WidgetLayoutInvalid(
                    "The layout widgets do not match the dashboard widgets."
                )
            delta_by_id[widget_id] = item

        merged_layout = [
            delta_by_id.get(widget.id, current_by_id[widget.id])
            for widget in self.widgets
        ]
        return current_layout, self.validate(
            merged_layout,
            enforce_vertical_bound=enforce_vertical_bound,
        )

    def apply(
        self,
        layout_by_widget_id: dict[int, WidgetLayoutDict],
        *,
        original_layout: list[WidgetLayoutDict] | None = None,
        allowed_widget_ids: set[int] | None = None,
    ) -> WidgetLayoutDelta:
        """Persists only rows whose geometry changed and returns that exact delta.

        ``layout_by_widget_id`` must come from :meth:`validate` or
        :meth:`merge_delta`. The optional ``original_layout`` may additionally
        contain a widget being deleted, which lets delete actions capture one
        coherent delta without rewriting any of the remaining rows.
        """

        widget_ids = {widget.id for widget in self.widgets}
        if set(layout_by_widget_id) != widget_ids:
            raise WidgetLayoutInvalid(
                "The layout widgets do not match the dashboard widgets."
            )

        if original_layout is None:
            original_layout = self.current_layout
        new_layout = [layout_by_widget_id[widget.id] for widget in self.widgets]
        layout_delta = WidgetLayoutDelta.between(original_layout, new_layout)
        changed_widget_ids = {item["id"] for item in layout_delta.new_layout}
        if allowed_widget_ids is not None and not changed_widget_ids.issubset(
            allowed_widget_ids
        ):
            raise WidgetLayoutInvalid(
                "The layout cannot modify a widget hidden from the user."
            )

        widgets_to_update = [
            widget for widget in self.widgets if widget.id in changed_widget_ids
        ]
        if widgets_to_update:
            updated_on = timezone.now()
            for widget in widgets_to_update:
                layout = layout_by_widget_id[widget.id]
                widget.grid_x = layout["grid_x"]
                widget.grid_y = layout["grid_y"]
                widget.grid_width = layout["grid_width"]
                widget.grid_height = layout["grid_height"]
                widget.updated_on = updated_on

            Widget.objects.bulk_update(
                widgets_to_update,
                [
                    "grid_x",
                    "grid_y",
                    "grid_width",
                    "grid_height",
                    "updated_on",
                ],
            )

        return layout_delta

    def apply_delta(
        self,
        layout_delta: list[WidgetLayoutDict],
        *,
        enforce_vertical_bound: bool = True,
        allowed_widget_ids: set[int] | None = None,
    ) -> WidgetLayoutDelta:
        """Merges a partial layout into the locked state and persists its delta."""

        original_layout, layout_by_widget_id = self.merge_delta(
            layout_delta,
            enforce_vertical_bound=enforce_vertical_bound,
        )
        return self.apply(
            layout_by_widget_id,
            original_layout=original_layout,
            allowed_widget_ids=allowed_widget_ids,
        )
