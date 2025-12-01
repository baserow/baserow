from typing import TYPE_CHECKING, Any, Dict, List, Optional

from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.api.rows.serializers import (
    RowHistorySerializer,
    RowSerializer,
    get_row_serializer_class,
    serialize_rows_for_response,
)
from baserow.contrib.database.rows import signals as row_signals
from baserow.contrib.database.rows.registries import row_metadata_registry
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.ws.registries import PageType, page_registry

if TYPE_CHECKING:
    from baserow.contrib.database.rows.models import RowHistory


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


class RealtimeRowMessages:
    """
    A collection of functions which construct the payloads for the realtime
    websocket messages related to rows.
    """

    @staticmethod
    def rows_deleted(
        table_id: int, serialized_rows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            "type": "rows_deleted",
            "table_id": table_id,
            "row_ids": [r["id"] for r in serialized_rows],
            "rows": serialized_rows,
        }

    @staticmethod
    def rows_created(
        table_id: int,
        serialized_rows: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        before: Optional[GeneratedTableModel],
    ) -> Dict[str, Any]:
        return {
            "type": "rows_created",
            "table_id": table_id,
            "rows": serialized_rows,
            "metadata": metadata,
            "before_row_id": before.id if before else None,
        }

    @staticmethod
    def rows_updated(
        table_id: int,
        serialized_rows_before_update: List[Dict[str, Any]],
        serialized_rows: List[Dict[str, Any]],
        metadata: Dict[int, Dict[str, Any]],
        updated_field_ids: List[int],
    ) -> Dict[str, Any]:
        return {
            "type": "rows_updated",
            "table_id": table_id,
            # The web-frontend expects a serialized version of the rows before it
            # was updated in order to estimate what position the row had in the
            # view.
            "rows_before_update": serialized_rows_before_update,
            "rows": serialized_rows,
            "metadata": metadata,
            "updated_field_ids": updated_field_ids,
        }

    @staticmethod
    def row_orders_recalculated(table_id: int) -> Dict[str, Any]:
        return {
            "type": "row_orders_recalculated",
            "table_id": table_id,
        }
