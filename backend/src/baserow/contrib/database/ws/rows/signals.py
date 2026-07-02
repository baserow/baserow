from functools import partial
from typing import TYPE_CHECKING, List

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.api.rows.serializers import (
    RowHistorySerializer,
    RowSerializer,
    get_row_serializer_class,
    serialize_rows_for_response,
)
from baserow.contrib.database.fields.dependencies.update_collector import (
    DependantRowsUpdate,
)
from baserow.contrib.database.rows import signals as row_signals
from baserow.contrib.database.rows.registries import row_metadata_registry
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.signals import table_updated
from baserow.contrib.database.ws.rows.messages import RealtimeRowMessages
from baserow.contrib.database.ws.rows.tasks import (
    DEPENDANT_ROWS_FORCE_REFRESH_DEBOUNCE_SECONDS,
    broadcast_dependant_rows_updated,
    dependant_rows_force_refresh_cache_key,
    send_trailing_force_table_refresh,
)
from baserow.ws.registries import PageType, page_registry

if TYPE_CHECKING:
    from baserow.contrib.database.rows.models import RowHistory

# Tables beyond this per-action maximum fall back to a whole-table refresh so
# the amount of serialization work stays bounded.
MAX_EXACT_DEPENDANT_TABLE_BROADCASTS = 10
# Per table, exact broadcasts beyond this per-debounce-window maximum degrade
# to the debounced refresh, so per-row driver loops (AI jobs, one-row-at-a-time
# integrations) can't flood the celery queue with serialization tasks.
MAX_EXACT_BROADCASTS_PER_TABLE_PER_WINDOW = 5


@receiver(row_signals.before_rows_update)
def serialize_rows_values(
    sender,
    rows,
    user,
    table,
    model,
    updated_field_ids,
    serialize_only_updated_fields: bool = False,
    **kwargs,
):
    return serialize_rows_for_response(
        rows,
        model,
        field_ids=updated_field_ids if serialize_only_updated_fields else None,
    )


@receiver(row_signals.rows_created)
def rows_created(
    sender,
    rows,
    before,
    user,
    table,
    model,
    send_realtime_update=True,
    send_webhook_events=True,
    **kwargs,
):
    if not send_realtime_update:
        return

    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            RealtimeRowMessages.rows_created(
                table_id=table.id,
                serialized_rows=get_row_serializer_class(
                    model, RowSerializer, is_response=True
                )(rows, many=True).data,
                metadata=row_metadata_registry.generate_and_merge_metadata_for_rows(
                    user, table, [row.id for row in rows]
                ),
                before=before,
            ),
            getattr(user, "web_socket_id", None),
            table_id=table.id,
        )
    )


@receiver(row_signals.rows_updated)
def rows_updated(
    sender,
    rows,
    user,
    table,
    model,
    before_return,
    updated_field_ids,
    send_realtime_update=True,
    serialize_only_updated_fields: bool = False,
    **kwargs,
):
    if not send_realtime_update:
        return

    table_page_type = page_registry.get("table")
    before_rows_values = dict(before_return)[serialize_rows_values]
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            RealtimeRowMessages.rows_updated(
                table_id=table.id,
                serialized_rows_before_update=before_rows_values,
                serialized_rows=get_row_serializer_class(
                    model,
                    RowSerializer,
                    is_response=True,
                    # in some cases the caller may want to serialize just the fields
                    # that were provided in updated_field_ids list (i.e. field rules).
                    # Otherwise, we need to serialize all fields (i.e. in webhooks).
                    field_ids=updated_field_ids
                    if serialize_only_updated_fields
                    else None,
                )(rows, many=True).data,
                # Broadcast a list of updated fields so that the listener can take
                # action even if the value didn't change.
                updated_field_ids=list(updated_field_ids),
                metadata=row_metadata_registry.generate_and_merge_metadata_for_rows(
                    user, table, [row.id for row in rows]
                ),
            ),
            getattr(user, "web_socket_id", None),
            table_id=table.id,
        )
    )


def _send_force_table_refresh_debounced(sender, table: Table):
    """
    Coalesces bursts of expensive whole-table refreshes: the first refreshes
    immediately, one trailing refresh delivers the final state.
    """

    def send_after_commit():
        leading_key = dependant_rows_force_refresh_cache_key(table.id, trailing=False)
        if cache.add(
            leading_key, True, timeout=DEPENDANT_ROWS_FORCE_REFRESH_DEBOUNCE_SECONDS
        ):
            table_updated.send(sender, table=table, user=None, force_table_refresh=True)
            return

        trailing_key = dependant_rows_force_refresh_cache_key(table.id, trailing=True)
        if cache.add(
            trailing_key,
            True,
            timeout=DEPENDANT_ROWS_FORCE_REFRESH_DEBOUNCE_SECONDS * 2,
        ):
            send_trailing_force_table_refresh.apply_async(
                args=[table.id],
                countdown=DEPENDANT_ROWS_FORCE_REFRESH_DEBOUNCE_SECONDS,
            )

    # Deciding post-commit stops rolled back transactions from consuming the
    # keys and guarantees a trailing task covers every suppressed event.
    transaction.on_commit(send_after_commit)


def _exact_broadcast_slot_available(table_id: int) -> bool:
    key = f"dependant_rows_exact_broadcasts:{table_id}"
    if cache.add(key, 1, timeout=DEPENDANT_ROWS_FORCE_REFRESH_DEBOUNCE_SECONDS):
        return True
    try:
        return cache.incr(key) <= MAX_EXACT_BROADCASTS_PER_TABLE_PER_WINDOW
    except ValueError:
        # The key expired between the add and the incr.
        return True


def _broadcast_exact_or_refresh_debounced(sender, update: DependantRowsUpdate):
    if _exact_broadcast_slot_available(update.table.id):
        broadcast_dependant_rows_updated.delay(
            table_id=update.table.id,
            row_ids=list(update.row_ids),
            updated_field_ids=list(update.field_ids),
        )
    else:
        _send_force_table_refresh_debounced(sender, update.table)


@receiver(row_signals.dependant_rows_updated)
def dependant_rows_updated(
    sender,
    user,
    table,
    dependant_rows_updates: List[DependantRowsUpdate],
    send_realtime_update: bool = True,
    **kwargs,
):
    """
    Broadcasts realtime events for rows changed by a dependency cascade so the
    affected tables' subscribers see the new values without refreshing.
    """

    if not send_realtime_update or not dependant_rows_updates:
        return
    if settings.DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT <= 0:
        return

    exact_broadcasts = 0
    for update in dependant_rows_updates:
        if (
            update.requires_refresh
            or exact_broadcasts >= MAX_EXACT_DEPENDANT_TABLE_BROADCASTS
        ):
            _send_force_table_refresh_debounced(sender, update.table)
        else:
            exact_broadcasts += 1
            transaction.on_commit(
                partial(_broadcast_exact_or_refresh_debounced, sender, update)
            )


@receiver(row_signals.rows_ai_values_generation_error)
def rows_ai_values_generation_error(
    sender, user, rows, field, table, error_message, **kwargs
):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            {
                "type": "rows_ai_values_generation_error",
                "field_id": field.id,
                "table_id": table.id,
                "row_ids": [row.id for row in rows],
                "error": error_message,
            },
            None,
            table_id=table.id,
        )
    )


@receiver(row_signals.before_rows_delete)
def before_rows_delete(sender, rows, user, table, model, **kwargs):
    return get_row_serializer_class(model, RowSerializer, is_response=True)(
        rows, many=True
    ).data


@receiver(row_signals.rows_deleted)
def rows_deleted(
    sender, rows, user, table, model, before_return, send_realtime_update=True, **kwargs
):
    if not send_realtime_update:
        return

    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            RealtimeRowMessages.rows_deleted(
                table_id=table.id,
                serialized_rows=dict(before_return)[before_rows_delete],
            ),
            getattr(user, "web_socket_id", None),
            table_id=table.id,
        )
    )


@receiver(row_signals.row_orders_recalculated)
def row_orders_recalculated(sender, table, **kwargs):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            RealtimeRowMessages.row_orders_recalculated(table_id=table.id),
            table_id=table.id,
        )
    )


@receiver(row_signals.rows_history_updated)
def rows_history_updated(
    sender,
    table_id,
    row_history_entries: "list[RowHistory]",
    **kwargs,
):
    row_page_type: PageType = page_registry.get("row")

    def send_rows():
        payloads_with_group_kws = [
            (
                {
                    "table_id": table_id,
                    "row_id": entry.row_id,
                },
                {
                    "type": "row_history_updated",
                    "row_history_entry": RowHistorySerializer(entry).data,
                    "table_id": table_id,
                    "row_id": entry.row_id,
                },
            )
            for entry in row_history_entries
        ]
        row_page_type.broadcast_many(
            payloads_with_group_kws,
            table_id=table_id,
        )

    transaction.on_commit(send_rows)
