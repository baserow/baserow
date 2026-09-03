from typing import TypedDict

from baserow.contrib.dashboard.data_sources.types import DashboardDataSourceDict
from baserow.core.integrations.types import IntegrationDict


class LegacyWidgetDict(TypedDict):
    """A widget export produced before persisted grid layouts existed."""

    id: int
    title: str
    description: str
    order: str
    type: str


class WidgetDict(LegacyWidgetDict):
    """The current serialized widget shape."""

    grid_x: int
    grid_y: int
    grid_width: int
    grid_height: int


class WidgetImportDict(LegacyWidgetDict, total=False):
    """The backward-compatible shape accepted by dashboard imports."""

    grid_x: int
    grid_y: int
    grid_width: int
    grid_height: int


class DashboardDict(TypedDict):
    id: int
    name: str
    description: str
    order: str
    type: str
    widgets: list[WidgetDict]
    integrations: list[IntegrationDict]
    data_sources: list[DashboardDataSourceDict]
