from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.api.rows.serializers import serialize_rows_for_response
from baserow.contrib.database.rows.signals import (
    rows_created,
    rows_deleted,
    rows_updated,
)

from .tasks import (
    two_way_sync_row_created,
    two_way_sync_row_deleted,
    two_way_sync_row_updated,
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
    skip_two_way_sync=False,
    **kwargs,
):
    if not table.is_two_way_data_synced_table:
        return

    # If set to True when the rows are created, updated, or deleted via a sync. In
    # that case, it's directly from the source table, and we don't want to re do the
    # operation in the source.
    if skip_two_way_sync:
        return

    transaction.on_commit(
        lambda: two_way_sync_row_created.delay(
            serialized_rows=serialize_rows_for_response(rows, model),
            data_sync_id=table.data_sync.id,
        )
    )


@receiver(rows_updated)
def rows_updated_receiver(
    sender,
    rows,
    user,
    table,
    model,
    before_return,
    updated_field_ids,
    send_realtime_update=True,
    send_webhook_events=True,
    m2m_change_tracker=None,
    skip_two_way_sync=False,
    **kwargs,
):
    if not table.is_two_way_data_synced_table:
        return

    # If set to True when the rows are created, updated, or deleted via a sync. In
    # that case, it's directly from the source table, and we don't want to maintain
    # duplicates.
    if skip_two_way_sync:
        return

    synced_properties_field_ids = [
        p.field_id for p in table.data_sync.synced_properties.all()
    ]
    any_synced_property_updated = any(
        updated_field_id in synced_properties_field_ids
        for updated_field_id in updated_field_ids
    )

    # If set to True when the rows are created, updated, or deleted via a sync. In
    # that case, it's directly from the source table, and we don't want to re do the
    # operation in the source.
    if not any_synced_property_updated:
        return

    transaction.on_commit(
        lambda: two_way_sync_row_updated.delay(
            serialized_rows=serialize_rows_for_response(rows, model),
            data_sync_id=table.data_sync.id,
            updated_field_ids=list(updated_field_ids),
        )
    )


@receiver(rows_deleted)
def rows_deleted_receiver(
    sender,
    rows,
    user,
    table,
    model,
    before_return,
    send_realtime_update=True,
    send_webhook_events=True,
    m2m_change_tracker=None,
    skip_two_way_sync=False,
    **kwargs,
):
    if not table.is_two_way_data_synced_table:
        return

    # If set to True when the rows are created, updated, or deleted via a sync. In
    # that case, it's directly from the source table, and we don't want to re do the
    # operation in the source.
    if skip_two_way_sync:
        return

    transaction.on_commit(
        lambda: two_way_sync_row_deleted.delay(
            serialized_rows=serialize_rows_for_response(rows, model),
            data_sync_id=table.data_sync.id,
        )
    )
