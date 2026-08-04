from typing import TypedDict

from baserow.contrib.dashboard.data_sources.types import DashboardDataSourceDict
from baserow.core.integrations.types import IntegrationDict


class WidgetDict(TypedDict):
    id: int
    title: str
    description: str
    order: str
    grid_x: int
    grid_y: int
    grid_width: int
    grid_height: int
    type: str


class DashboardDict(TypedDict):
    id: int
    name: str
    description: str
    order: str
    type: str
    widgets: list[WidgetDict]
    integrations: list[IntegrationDict]
    data_sources: list[DashboardDataSourceDict]
