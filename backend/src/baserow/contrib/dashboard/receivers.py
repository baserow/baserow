from django.db import transaction
from django.db.models.signals import post_delete, post_save
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


@receiver(post_save)
@receiver(post_delete)
def invalidate_changed_widget_properties(sender, instance, **kwargs):
    """Invalidate formula extraction for all widget subclasses, including trash edits."""
    from baserow.contrib.dashboard.formula_property_extractor import (
        invalidate_widget_properties,
    )
    from baserow.contrib.dashboard.widgets.models import Widget

    if not isinstance(instance, Widget):
        return
    widget_id = instance.id
    invalidate_widget_properties(widget_id)
    # A concurrent reader can still see the old database state before commit.
    transaction.on_commit(lambda: invalidate_widget_properties(widget_id))


@receiver(post_save)
@receiver(post_delete)
def invalidate_source_widget_properties(sender, instance, **kwargs):
    """A source change can alter any widget's referenced service or property paths."""
    from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
    from baserow.contrib.dashboard.formula_property_extractor import (
        invalidate_widget_properties,
    )
    from baserow.contrib.dashboard.widgets.models import Widget

    if not isinstance(instance, DashboardDataSource):
        return
    widget_ids = list(
        Widget.objects_and_trash.filter(dashboard_id=instance.dashboard_id).values_list(
            "id", flat=True
        )
    )
    for widget_id in widget_ids:
        invalidate_widget_properties(widget_id)

    def invalidate_after_commit():
        for widget_id in widget_ids:
            invalidate_widget_properties(widget_id)

    transaction.on_commit(invalidate_after_commit)
