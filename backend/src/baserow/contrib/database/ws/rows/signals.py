import dataclasses
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Set

from django.conf import settings
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
    merge_dependant_rows_updates,
)
from baserow.contrib.database.rows import signals as row_signals
from baserow.contrib.database.rows.registries import row_metadata_registry
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.signals import table_updated
from baserow.contrib.database.ws.rows.messages import RealtimeRowMessages
from baserow.contrib.database.ws.rows.tasks import broadcast_dependant_rows_updated
from baserow.contrib.database.ws.views.rows.handler import (
    DependantRowsViewChange,
    ViewRealtimeRowsHandler,
)
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
    _mark_rows_written_directly(table.id, (row.id for row in rows))
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
    _mark_rows_written_directly(table.id, (row.id for row in rows))
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


class TableWritesInTransaction:
    """
    Who wrote a table's rows in the current transaction. A broadcast only decides
    the rows nothing else wrote: another write makes its snapshot or decision stale.
    """

    def __init__(self, table_id: int) -> None:
        """
        :param table_id: The id of the table.
        """

        self.table_id = table_id
        self.broadcasts: List["DependantRowsBroadcast"] = []
        self.row_ids_written_directly: Set[int] = set()
        # Set by bulk writes and by an overflowing broadcast, whose rows are unknown.
        self.all_rows_written = False

    def __call__(self) -> None:
        """
        Registered on commit only so the transaction's writers can find it.
        """

    def get_row_ids_written_by_others(
        self, broadcast: "DependantRowsBroadcast"
    ) -> Set[int]:
        """
        :param broadcast: One of the table's broadcasts.
        :return: The ids of its rows that something else wrote too.
        """

        if self.all_rows_written:
            return broadcast.get_listed_row_ids()
        return self.row_ids_written_directly.union(
            *(
                other.get_listed_row_ids()
                for other in self.broadcasts
                if other is not broadcast
            )
        )


def _get_table_writes(table_id: int) -> TableWritesInTransaction:
    """
    :param table_id: The id of the table.
    :return: The table's writes in the current transaction.
    """

    for _, callback, _ in transaction.get_connection().run_on_commit:
        if (
            isinstance(callback, TableWritesInTransaction)
            and callback.table_id == table_id
        ):
            return callback
    table_writes = TableWritesInTransaction(table_id)
    transaction.on_commit(table_writes)
    return table_writes


def _is_tracking_table_writes() -> bool:
    """
    :return: Whether a later cascade in this transaction could be broadcast.
    """

    return (
        settings.DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT > 0
        and transaction.get_connection().in_atomic_block
    )


def _mark_rows_written_directly(table_id: int, row_ids: Iterable[int]) -> None:
    """
    :param table_id: The id of the table of the rows.
    :param row_ids: The ids of the rows created, updated or deleted directly.
    """

    if _is_tracking_table_writes():
        _get_table_writes(table_id).row_ids_written_directly.update(row_ids)


class DependantRowsBroadcast:
    """
    A transaction's cascades into a table, broadcast as one update on commit so
    clients never get an in-between before state.
    """

    def __init__(self, sender: Any, table: Table) -> None:
        """
        :param sender: The sender of the first signal.
        :param table: The table the cascades changed.
        """

        self.sender = sender
        self.table = table
        self.updates: List[DependantRowsUpdate] = []
        self.visibility_changes: List[DependantRowsViewChange] = []
        self.savepoint_ids: Set[str] = set(transaction.get_connection().savepoint_ids)
        self.table_writes = _get_table_writes(table.id)
        self.table_writes.broadcasts.append(self)

    def is_joinable(self) -> bool:
        """
        :return: False inside a newer savepoint, which could roll back the cascade
            but not the broadcast.
        """

        return set(transaction.get_connection().savepoint_ids) <= self.savepoint_ids

    def add(self, update: DependantRowsUpdate) -> None:
        """
        Decides the view changes now, while the cascades still lock the rows.

        :param update: A cascade update of the table.
        :return: None, sets `visibility_changes`.
        """

        self.updates.append(update)
        merged_update = self.get_merged_update()
        if merged_update is not None and merged_update.requires_refresh:
            self.table_writes.all_rows_written = True
        self.visibility_changes = (
            []
            if merged_update is None or merged_update.requires_refresh
            else ViewRealtimeRowsHandler().get_dependant_rows_visibility_changes(
                dataclasses.replace(
                    merged_update,
                    field_ids_with_unknown_before_values=(
                        self.get_transaction_field_ids_with_unknown_before_values()
                    ),
                )
            )
        )

    def get_transaction_field_ids_with_unknown_before_values(self) -> Set[int]:
        """
        :return: The field ids of every broadcast so far, closed ones included.
        """

        return {
            field_id
            for broadcast in [self, *_get_dependant_rows_broadcasts(self.table.id)]
            for update in broadcast.updates
            for field_id in update.field_ids_with_unknown_before_values
        }

    def get_merged_update(self) -> Optional[DependantRowsUpdate]:
        """
        :return: The merged update, None if no row changed.
        """

        merged_updates = merge_dependant_rows_updates(self.updates)
        return merged_updates[0] if merged_updates else None

    def get_listed_row_ids(self) -> Set[int]:
        """
        :return: The ids of the rows the cascades changed.
        """

        return {row_id for update in self.updates for row_id in update.row_ids}

    def __call__(self) -> None:
        """
        View enter and leave events go first, since the task sending the new
        values can run after later commits.

        :return: None.
        """

        update = self.get_merged_update()
        if update is None:
            return
        handler = ViewRealtimeRowsHandler()
        if update.requires_refresh:
            table_updated.send(
                self.sender, table=self.table, user=None, force_table_refresh=True
            )
            handler.broadcast_force_rows_refresh_to_views(self.table)
            return
        row_ids_written_by_others = self.table_writes.get_row_ids_written_by_others(
            self
        )
        for view, rows, to_message in self.visibility_changes:
            rows = [row for row in rows if row["id"] not in row_ids_written_by_others]
            if rows:
                handler.broadcast_to_types(view, to_message(rows))
        broadcast_dependant_rows_updated.delay(
            table_id=update.table.id,
            row_ids=list(update.row_ids),
            updated_field_ids=list(update.field_ids),
            serialized_rows_before=list(update.before_rows.values()),
        )


def _get_dependant_rows_broadcasts(table_id: int) -> List[DependantRowsBroadcast]:
    """
    :param table_id: The id of the table.
    :return: The table's broadcasts pending on commit, in order.
    """

    return [
        callback
        for _, callback, _ in transaction.get_connection().run_on_commit
        if isinstance(callback, DependantRowsBroadcast)
        and callback.table.id == table_id
    ]


def _get_latest_dependant_rows_broadcast(
    table_id: int,
) -> Optional[DependantRowsBroadcast]:
    """
    :param table_id: The id of the table.
    :return: The table's latest pending broadcast, if any.
    """

    broadcasts = _get_dependant_rows_broadcasts(table_id)
    return broadcasts[-1] if broadcasts else None


@receiver(table_updated)
def table_rows_written_in_bulk(sender, table, force_table_refresh=False, **kwargs):
    """
    A forced refresh means rows were written in bulk, without their ids.
    """

    if force_table_refresh and _is_tracking_table_writes():
        _get_table_writes(table.id).all_rows_written = True


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
    affected tables' subscribers see the new values without refreshing. Tables
    with more affected rows than the limit receive a whole-table refresh instead.
    """

    if not send_realtime_update or not dependant_rows_updates:
        return
    if settings.DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT <= 0:
        return

    for update in dependant_rows_updates:
        broadcast = _get_latest_dependant_rows_broadcast(update.table.id)
        if broadcast is not None and broadcast.is_joinable():
            broadcast.add(update)
        else:
            broadcast = DependantRowsBroadcast(sender, update.table)
            broadcast.add(update)
            transaction.on_commit(broadcast)


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
    _mark_rows_written_directly(table.id, (row.id for row in rows))
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
