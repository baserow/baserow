from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.signals import class_prepared, post_delete, post_save
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


def invalidate_changed_widget_properties(sender, instance, **kwargs):
    """Invalidate formula extraction for all widget subclasses, including trash edits."""
    from baserow.contrib.dashboard.formula_property_extractor import (
        invalidate_widget_properties,
    )
    from baserow.contrib.dashboard.widgets.models import (
        Widget,
        WidgetFilterCondition,
        WidgetFilterGroup,
        WidgetFilterTarget,
    )

    if isinstance(
        instance, (WidgetFilterTarget, WidgetFilterGroup, WidgetFilterCondition)
    ):
        # Cascade deletion can already have removed the owner; no cache remains
        # useful in that case, and the widget's own signal handles invalidation.
        try:
            instance = instance.get_widget()
        except ObjectDoesNotExist:
            return
    if not isinstance(instance, Widget):
        return
    from baserow.contrib.dashboard.widgets.handler import WidgetHandler

    WidgetHandler.invalidate_widgets_cache(instance.dashboard_id)
    widget_id = instance.id
    invalidate_widget_properties(widget_id)
    # A concurrent reader can still see the old database state before commit.
    transaction.on_commit(lambda: invalidate_widget_properties(widget_id))


@receiver(post_save, sender="dashboard.DashboardDataSource")
@receiver(post_delete, sender="dashboard.DashboardDataSource")
def invalidate_source_widget_properties(sender, instance, **kwargs):
    """A source change can alter any widget's referenced service or property paths."""
    from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
    from baserow.contrib.dashboard.formula_property_extractor import (
        invalidate_widget_properties,
    )
    from baserow.contrib.dashboard.widgets.models import Widget

    if not isinstance(instance, DashboardDataSource):
        return
    from baserow.contrib.dashboard.widgets.handler import WidgetHandler

    WidgetHandler.invalidate_widgets_cache(instance.dashboard_id)
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


@receiver(class_prepared)
def connect_widget_property_receivers(sender, **kwargs):
    """Limit mutation listeners to widget models, including future subclasses.

    A global post_delete listener disables Django's fast cascade deletion for
    unrelated models. Register explicit senders so inherited model deletion
    keeps its normal cascade behavior outside dashboard widgets.
    """
    from baserow.contrib.dashboard.widgets.models import (
        Widget,
        WidgetFilterCondition,
        WidgetFilterGroup,
        WidgetFilterTarget,
    )

    if not issubclass(sender, Widget) and sender not in (
        WidgetFilterTarget,
        WidgetFilterGroup,
        WidgetFilterCondition,
    ):
        return
    for signal in (post_save, post_delete):
        signal.connect(
            invalidate_changed_widget_properties,
            sender=sender,
            dispatch_uid=f"dashboard_widget_properties_{sender._meta.label_lower}",
        )


# Models are already loaded when DashboardConfig.ready imports this module.
for model in apps.get_models():
    connect_widget_property_receivers(model)
