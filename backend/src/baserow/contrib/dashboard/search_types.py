from baserow.contrib.dashboard.models import Dashboard
from baserow.core.search.search_types import ApplicationSearchType


class DashboardSearchType(ApplicationSearchType):
    """
    Searchable item type specifically for dashboards.
    """

    type = "dashboard"
    name = "Dashboard"
    model_class = Dashboard
    priority = 3
