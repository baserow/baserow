from dataclasses import dataclass
from typing import NewType

from .models import Widget

WidgetForUpdate = NewType("WidgetForUpdate", Widget)


@dataclass
class UpdatedWidget:
    widget: Widget
    original_values: dict[str, any]
    new_values: dict[str, any]
