from typing import TypedDict


class WidgetDict(TypedDict):
    id: int
    order: int
    type: str


class DashboardDict(TypedDict):
    id: int
    name: str
    description: str
    order: int
    type: str
