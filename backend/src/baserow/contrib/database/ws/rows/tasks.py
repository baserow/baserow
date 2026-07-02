from typing import List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import DEFAULT_DB_ALIAS

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from baserow.config.celery import app
from baserow.config.db_routers import set_db_alias
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.rows.registries import row_metadata_registry
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.signals import table_updated
from baserow.contrib.database.ws.rows.messages import RealtimeRowMessages
from baserow.ws.registries import page_registry
from baserow.ws.tasks import ChannelGroupMessage, send_messages_to_channel_group

DEPENDANT_ROWS_FORCE_REFRESH_DEBOUNCE_SECONDS = 5


def dependant_rows_force_refresh_cache_key(table_id: int, trailing: bool) -> str:
    suffix = ":trailing" if trailing else ""
    return f"dependant_rows_force_refresh:{table_id}{suffix}"


def _get_table(table_id: int) -> Optional[Table]:
    try:
        return Table.objects.get(pk=table_id)
    except Table.DoesNotExist:
        return None


@app.task(bind=True)
def broadcast_dependant_rows_updated(
    self,
    table_id: int,
    row_ids: List[int],
    updated_field_ids: List[int],
):
    """
    Serializes the current values of the provided rows and broadcasts them as
    regular rows_updated messages to the subscribers of the table's page.
    """

    table_page_type = page_registry.get("table")
    group_name = table_page_type.get_group_name(table_id)
    channel_layer = get_channel_layer()

    # Replicas can lag behind the commit that queued this task, in which case
    # stale values would be broadcast as the new state with no correction.
    set_db_alias(DEFAULT_DB_ALIAS)

    table = _get_table(table_id)
    if table is None:
        return

    model = table.get_model()
    rows = list(
        model.objects.filter(id__in=row_ids).enhance_by_fields(
            only_field_ids=updated_field_ids or None
        )
    )
    if not rows:
        return

    # Only the changed fields are serialized (the frontend merges partial rows
    # onto its buffered state), and rows are chunked so a raised limit setting
    # can never produce one unbounded websocket message.
    row_serializer = get_row_serializer_class(
        model,
        RowSerializer,
        is_response=True,
        field_ids=updated_field_ids or None,
    )
    messages = []
    chunk_size = settings.BATCH_ROWS_SIZE_LIMIT
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        payload = RealtimeRowMessages.rows_updated(
            table_id=table_id,
            # The values before the cascade are unknown here; the frontend
            # falls back to its own buffered state for id-only before rows.
            serialized_rows_before_update=[{"id": row.id} for row in chunk],
            serialized_rows=row_serializer(chunk, many=True).data,
            metadata=row_metadata_registry.generate_and_merge_metadata_for_rows(
                None, table, [row.id for row in chunk]
            ),
            updated_field_ids=updated_field_ids,
        )
        messages.append(
            ChannelGroupMessage(
                group_name,
                {
                    "type": "broadcast_to_group",
                    "payload": payload,
                    # The acting user's response lacks dependant values:
                    # exclude no socket.
                    "ignore_web_socket_id": None,
                    "exclude_user_ids": None,
                },
            )
        )
    async_to_sync(send_messages_to_channel_group)(channel_layer, messages)


@app.task(bind=True)
def send_trailing_force_table_refresh(self, table_id: int):
    """
    Sends the trailing refresh after a debounced burst of dependant row
    changes, so subscribers end up with the final state.
    """

    cache.delete(dependant_rows_force_refresh_cache_key(table_id, trailing=True))

    set_db_alias(DEFAULT_DB_ALIAS)
    table = _get_table(table_id)
    if table is None:
        return

    table_updated.send(None, table=table, user=None, force_table_refresh=True)
