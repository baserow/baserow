from baserow.contrib.database.data_sync.registries import TwoWaySyncStrategy


class RealtimePushTwoWaySyncStrategy(TwoWaySyncStrategy):
    """
    Two-way data sync strategy that pushes the changed made in the synced table
    directly to the source data using a celery task. The changes made in the source
    table must be synced in periodically or manually. This strategy is perfect for
    systems where you can write to, but not receive real-time events.
    """

    type = "realtime_push"
