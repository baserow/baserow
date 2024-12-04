from typing import NewType

from .models import Widget

WidgetForUpdate = NewType("WidgetForUpdate", Widget)
