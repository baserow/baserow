from django.db import transaction

from baserow.contrib.database.data_sync.registries import (
    TwoWaySyncStrategy,
    data_sync_type_registry,
)
from baserow.contrib.database.rows.handler import RowHandler


class RealtimePushTwoWaySyncStrategy(TwoWaySyncStrategy):
    """
    Two-way data sync strategy that pushes the changes made in the synced table
    directly to the data sync source. It's a simple implementation that just uses the
    data sync type to create everything is real-time.

    The changes made in the source table must be synced in periodically or manually.
    This strategy is perfect for systems where you can write to, but not receive
    real-time events. Because the source table will always be up to date, there will
    be no conflicts.
    """

    type = "realtime_push"

    def rows_created(self, serialized_rows, data_sync):
        data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)
        rows_to_update = data_sync_type.create_rows(serialized_rows, data_sync)

        if rows_to_update is None:
            return

        rows_to_update = [
            row
            for row in rows_to_update
            # Filter out the objects that don't contain any updates.
            if row and not (len(row) == 1 and "id" in row)
        ]

        if len(rows_to_update) == 0:
            return

        with transaction.atomic():
            RowHandler().force_update_rows(
                user=None,
                table=data_sync.table,
                rows_values=rows_to_update,
            )

    def rows_updated(self, serialized_rows, data_sync, updated_field_ids):
        data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)
        data_sync_type.update_rows(serialized_rows, data_sync, updated_field_ids)

    def rows_deleted(self, serialized_rows, data_sync):
        data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)
        data_sync_type.delete_rows(serialized_rows, data_sync)
