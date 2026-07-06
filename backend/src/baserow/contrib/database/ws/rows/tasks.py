from typing import Any, Dict, List, Optional

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
from baserow.contrib.database.ws.rows.messages import RealtimeRowMessages
from baserow.ws.registries import page_registry
from baserow.ws.tasks import ChannelGroupMessage, send_messages_to_channel_group


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
    serialized_rows_before: Optional[List[Dict[str, Any]]] = None,
):
    """
    Serializes the current values of the provided rows and broadcasts them as a
    regular rows_updated message to the subscribers of the table's page.

    :param table_id: The id of the table the rows belong to.
    :param row_ids: The ids of the rows whose values changed.
    :param updated_field_ids: The ids of the fields whose values changed.
    :param serialized_rows_before: Serialized pre-cascade state per row; rows
        without a snapshot fall back to an id-only skeleton before row.
    """

    # Replicas can lag behind the commit that queued this task, in which case
    # stale values would be broadcast as the new state with no correction.
    set_db_alias(DEFAULT_DB_ALIAS)

    table = _get_table(table_id)
    if table is None:
        return

    model = table.get_model()
    rows = list(model.objects.filter(id__in=row_ids).enhance_by_fields())
    if not rows:
        return

    table_page_type = page_registry.get("table")
    channel_layer = get_channel_layer()
    before_by_id = {row["id"]: row for row in (serialized_rows_before or [])}
    payload = RealtimeRowMessages.rows_updated(
        table_id=table_id,
        # Rows without a snapshot fall back to an id-only skeleton.
        serialized_rows_before_update=[
            before_by_id.get(row.id, {"id": row.id}) for row in rows
        ],
        serialized_rows=get_row_serializer_class(
            model, RowSerializer, is_response=True
        )(rows, many=True).data,
        metadata=row_metadata_registry.generate_and_merge_metadata_for_rows(
            None, table, [row.id for row in rows]
        ),
        updated_field_ids=updated_field_ids,
    )
    async_to_sync(send_messages_to_channel_group)(
        channel_layer,
        ChannelGroupMessage(
            table_page_type.get_group_name(table_id),
            {
                "type": "broadcast_to_group",
                "payload": payload,
                "ignore_web_socket_id": None,
                "exclude_user_ids": None,
            },
        ),
    )
