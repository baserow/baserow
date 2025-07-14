import traceback

from django.dispatch import receiver

from baserow.contrib.database.rows.signals import (
    rows_created,
    rows_deleted,
    rows_updated,
)


@receiver(rows_created)
def rows_created_receiver(
    sender,
    rows,
    before,
    user,
    table,
    model,
    send_realtime_update=True,
    send_webhook_events=True,
    m2m_change_tracker=None,
    **kwargs,
):
    if not table.is_data_synced_table:
        return

    print("rows created")


@receiver(rows_updated)
def rows_updated_receiver(
    sender,
    rows,
    user,
    table,
    model,
    before_return,
    updated_field_ids,
    m2m_change_tracker=None,
    **kwargs,
):
    if not table.is_data_synced_table:
        return

    print("rows updated")


@receiver(rows_deleted)
def rows_deleted_receiver(
    sender,
    rows,
    user,
    table,
    model,
    before_return,
    m2m_change_tracker=None,
    **kwargs,
):
    if not table.is_data_synced_table:
        return

    print("rows deleted")
