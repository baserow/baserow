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
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.signals import (
    view_filter_created,
    view_filter_deleted,
    view_filter_group_created,
    view_filter_group_deleted,
    view_filter_group_updated,
    view_filter_updated,
    view_updated,
)

from .handler import ViewSubscriptionHandler


def _notify_table_data_updated(table: Table, model: GeneratedTableModel | None = None):
    """
    Notifies the table views that the table data has been updated. This will result in
    the table views to be updated and the subscribers to be notified.

    :param table: The table for which the data has been updated.
    :param model: The model that was updated if available.
    """

    ViewSubscriptionHandler.notify_table_views_updates(
        table.view_set.all(), model=model
    )


def _notify_view_results_updated(view: View):
    """
    Notify the table view that the results of the view have been updated. This will
    result in the subscribers to be notified.

    :param view: The view for which the results have been updated.
    """

    ViewSubscriptionHandler.notify_table_views_updates([view])


@receiver([rows_updated, rows_created, rows_deleted])
def notify_rows_signals(sender, rows, user, table, model, dependant_fields, **kwargs):
    _notify_table_data_updated(table, model)

    updated_tables = set()
    for field in dependant_fields:
        updated_tables.add(field.table)
    for updated_table in updated_tables:
        _notify_table_data_updated(updated_table)


@receiver(view_updated)
def notify_view_updated(sender, view, user, old_view, **kwargs):
    _notify_view_results_updated(view)


@receiver([view_filter_created, view_filter_updated, view_filter_deleted])
def notify_view_filter_created_or_updated(sender, view_filter, user, **kwargs):
    _notify_view_results_updated(view_filter.view)


@receiver(
    [view_filter_group_created, view_filter_group_updated, view_filter_group_deleted]
)
def notify_view_filter_group_created_or_updated(
    sender, view_filter_group, user, **kwargs
):
    _notify_view_results_updated(view_filter_group.view)


def _notify_tables_of_fields_updated_or_deleted(field, related_fields, user, **kwargs):
    tables_to_notify = set([field.table])
    for updated_field in related_fields:
        tables_to_notify.add(updated_field.table)
    for table in tables_to_notify:
        _notify_table_data_updated(table)


@receiver([field_restored, field_updated])
def notify_field_updated(sender, field, related_fields, user, **kwargs):
    _notify_tables_of_fields_updated_or_deleted(field, related_fields, user, **kwargs)


@receiver(field_deleted)
def notify_field_deleted(sender, field_id, field, related_fields, user, **kwargs):
    _notify_tables_of_fields_updated_or_deleted(field, related_fields, user, **kwargs)
