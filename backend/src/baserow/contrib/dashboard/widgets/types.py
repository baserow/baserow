from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType

from .models import Widget

if TYPE_CHECKING:
    from baserow.contrib.dashboard.models import Dashboard

WidgetForUpdate = NewType("WidgetForUpdate", Widget)


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
class UpdatedWidgetLayout:
    dashboard: "Dashboard"
    widgets: list[Widget]
    original_layout: list[dict[str, int]]
    new_layout: list[dict[str, int]]
    deleted_widget: Widget | None = None
