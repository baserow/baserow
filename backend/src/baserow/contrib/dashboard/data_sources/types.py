from dataclasses import dataclass, field
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


@dataclass
class UpdatedDashboardDataSource:
    data_source: DashboardDataSource
    original_values: dict[str, any]
    new_values: dict[str, any]
    original_filter_links: dict[str, list] = field(default_factory=dict)
    updated_filter_widgets: list = field(default_factory=list)
