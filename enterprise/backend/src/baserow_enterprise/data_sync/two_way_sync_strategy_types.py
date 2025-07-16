from baserow.contrib.database.data_sync.registries import (
    TwoWaySyncStrategy,
    data_sync_type_registry,
)


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
        data_sync_type.create_rows(serialized_rows, data_sync)

    def rows_updated(self, serialized_rows, data_sync, updated_field_ids):
        data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)
        data_sync_type.update_rows(serialized_rows, data_sync, updated_field_ids)

    def rows_deleted(self, serialized_rows, data_sync):
        data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)
        data_sync_type.delete_rows(serialized_rows, data_sync)
