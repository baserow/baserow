from django.db import models

from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.widgets.models import SummaryWidget, Widget
from baserow.core.models import Application

__all__ = ["Dashboard", "DashboardDataSource", "SummaryWidget", "Widget"]


class Dashboard(Application):
    description = models.TextField(blank=True, db_default="")

    def get_parent(self):
        # Parent is the Application here even if it's at the "same" level
        # but it's a more generic type
        return self.application_ptr
