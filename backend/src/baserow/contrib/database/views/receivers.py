from django.dispatch import receiver

from baserow.contrib.database.fields.signals import (
    field_deleted,
    field_restored,
    field_updated,
)
from baserow.contrib.database.rows.signals import (
    rows_created,
    rows_deleted,
    rows_updated,
)
from baserow.contrib.database.table.signals import table_data_updated
from baserow.contrib.database.views.signals import (
    view_filter_created,
    view_filter_deleted,
    view_filter_group_created,
    view_filter_group_deleted,
    view_filter_group_updated,
    view_filter_updated,
    view_results_updated,
    view_updated,
)

from .handler import ViewSubscriptionHandler


@receiver([rows_updated, rows_created, rows_deleted])
def notify_rows_signals(sender, rows, user, table, model, dependant_fields, **kwargs):
    table_data_updated.send(
        sender=table, user=user, table=table, model=model, rows=rows
    )
    other_tables = set()
    for field in dependant_fields:
        other_tables.add(field.table)
    for other_table in other_tables:
        table_data_updated.send(sender=other_table, user=user, table=other_table)


@receiver(view_updated)
def notify_view_updated(sender, view, user, old_view, **kwargs):
    view_results_updated.send(sender=view, user=user, view=view)


@receiver([view_filter_created, view_filter_updated])
def notify_view_filter_created_or_updated(sender, view_filter, user, **kwargs):
    view_results_updated.send(sender=view_filter.view, user=user, view=view_filter.view)


@receiver(view_filter_deleted)
def notify_view_filter_deleted(sender, view_filter_id, view_filter, user, **kwargs):
    view_results_updated.send(sender=view_filter.view, user=user, view=view_filter.view)


@receiver([view_filter_group_created, view_filter_group_updated])
def notify_view_filter_group_created_or_updated(
    sender, view_filter_group, user, **kwargs
):
    view_results_updated.send(
        sender=view_filter_group.view, user=user, view=view_filter_group.view
    )


@receiver(view_filter_group_deleted)
def notify_view_filter_group_deleted(
    sender, view_filter_group_id, view_filter_group, user, **kwargs
):
    view_results_updated.send(
        sender=view_filter_group.view, user=user, view=view_filter_group.view
    )


def _notify_tables_of_fields_updated_or_deleted(field, related_fields, user, **kwargs):
    tables_to_notify = set([field.table])
    for related_field in related_fields:
        tables_to_notify.add(related_field.table)
    for table in tables_to_notify:
        table_data_updated.send(sender=table, user=user, table=table)


@receiver([field_restored, field_updated])
def notify_field_updated(sender, field, related_fields, user, **kwargs):
    _notify_tables_of_fields_updated_or_deleted(field, related_fields, user, **kwargs)


@receiver(field_deleted)
def notify_field_deleted(sender, field_id, field, related_fields, user, **kwargs):
    _notify_tables_of_fields_updated_or_deleted(field, related_fields, user, **kwargs)


@receiver(table_data_updated)
def notify_table_data_updated(sender, user, table, **kwargs):
    ViewSubscriptionHandler.notify_table_views_updates(
        table.view_set.all(), kwargs.get("model", None)
    )


@receiver(view_results_updated)
def notify_view_results_updated(sender, user, view, **kwargs):
    ViewSubscriptionHandler.notify_table_views_updates([view])
