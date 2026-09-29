from django.dispatch import receiver

from baserow.contrib.dashboard.last_viewed_types import (
    DashboardLastViewedItemType,
)
from baserow.contrib.dashboard.signals import dashboard_loaded
from baserow.core.last_viewed.handler import LastViewedHandler


@receiver(dashboard_loaded)
def dashboard_loaded_mark_last_viewed(sender, dashboard_id, user, **kwargs):
    LastViewedHandler.schedule_mark_viewed(
        user, DashboardLastViewedItemType.type, dashboard_id
    )
