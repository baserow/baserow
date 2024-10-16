from typing import NewType

from .models import DashboardDataSource

DashboardDataSourceForUpdate = NewType(
    "DashboardDataSourceForUpdate", DashboardDataSource
)
