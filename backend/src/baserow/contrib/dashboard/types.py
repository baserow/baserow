from typing import TypedDict

from baserow.core.services.types import ServiceDictSubClass


class WidgetDict(TypedDict):
    id: int
    order: int
    type: str


class DashboardDataSourceDict(TypedDict):
    id: int
    name: str
    order: int
    service: ServiceDictSubClass | None


class DashboardDict(TypedDict):
    id: int
    name: str
    description: str
    order: int
    type: str
