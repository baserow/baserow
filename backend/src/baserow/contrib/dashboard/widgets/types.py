from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType, TypedDict

from .models import Widget

if TYPE_CHECKING:
    from baserow.contrib.dashboard.models import Dashboard

WidgetForUpdate = NewType("WidgetForUpdate", Widget)


class WidgetLayoutDict(TypedDict):
    """The persisted geometry of one dashboard widget."""

    id: int
    grid_x: int
    grid_y: int
    grid_width: int
    grid_height: int


@dataclass(frozen=True)
class WidgetGridLayout:
    """The grid constraints and default size for a dashboard widget type."""

    default_width: int
    default_height: int
    min_width: int
    min_height: int
    max_width: int
    max_height: int

    def as_dict(self) -> dict[str, int]:
        return {
            "default_width": self.default_width,
            "default_height": self.default_height,
            "min_width": self.min_width,
            "min_height": self.min_height,
            "max_width": self.max_width,
            "max_height": self.max_height,
        }


@dataclass
class UpdatedWidget:
    widget: Widget
    original_values: dict[str, any]
    new_values: dict[str, any]


@dataclass
class CreatedWidget:
    widget: Widget
    layout_delta: "WidgetLayoutDelta"


@dataclass(frozen=True)
class WidgetLayoutDelta:
    """Only the widget geometries changed by one atomic layout mutation."""

    original_layout: list[WidgetLayoutDict]
    new_layout: list[WidgetLayoutDict]

    @property
    def has_changes(self) -> bool:
        return bool(self.original_layout or self.new_layout)

    @classmethod
    def between(
        cls,
        original_layout: list[WidgetLayoutDict],
        new_layout: list[WidgetLayoutDict],
    ) -> "WidgetLayoutDelta":
        original_by_id = {item["id"]: item for item in original_layout}
        new_by_id = {item["id"]: item for item in new_layout}
        changed_ids = sorted(
            widget_id
            for widget_id in original_by_id.keys() | new_by_id.keys()
            if original_by_id.get(widget_id) != new_by_id.get(widget_id)
        )
        return cls(
            [
                dict(original_by_id[widget_id])
                for widget_id in changed_ids
                if widget_id in original_by_id
            ],
            [
                dict(new_by_id[widget_id])
                for widget_id in changed_ids
                if widget_id in new_by_id
            ],
        )


@dataclass
class UpdatedWidgetLayout:
    dashboard: "Dashboard"
    layout_delta: WidgetLayoutDelta
    visible_layout: list[WidgetLayoutDict] | None = None
    deleted_widget: Widget | None = None
