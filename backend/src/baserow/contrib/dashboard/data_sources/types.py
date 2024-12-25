from typing import NewType, TypedDict

from baserow.core.services.types import ServiceDictSubClass

from .models import DashboardDataSource

DashboardDataSourceForUpdate = NewType(
    "DashboardDataSourceForUpdate", DashboardDataSource
)


class DashboardDataSourceDict(TypedDict):
    id: int
    name: str
    order: str
    service: ServiceDictSubClass
