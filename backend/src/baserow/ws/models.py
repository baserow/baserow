from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models


class RealtimeEvent(models.Model):
    UNLOGGED = True

    id = models.BigAutoField(primary_key=True)
    channel_group = models.TextField()
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    # The ws_set_realtime_event_targets() pg-trigger populates these from payload on
    # insert/update
    target_user_ids = ArrayField(
        models.IntegerField(), default=list, db_default=[], editable=False
    )
    all_users = models.BooleanField(default=False, db_default=False, editable=False)

    class Meta:
        db_table = "ws_realtime_events"
        indexes = [
            models.Index(
                fields=["channel_group", "id"],
                name="ws_realtime_channel_group_idx",
            ),
            # Only shared users-channel events need recipient indexes. Page
            # events use group/id, and no full business payload is indexed.
            GinIndex(
                fields=["target_user_ids"],
                condition=models.Q(channel_group="users"),
                name="ws_realtime_targets_idx",
            ),
            models.Index(
                fields=["id"],
                condition=models.Q(channel_group="users", all_users=True),
                name="ws_realtime_all_users_idx",
            ),
            models.Index(
                fields=["created_at", "id"],
                name="ws_realtime_created_id_idx",
            ),
        ]


class RealtimeEventHistorySummary(models.Model):
    """Expired event maxima for an exact audience, without business payloads."""

    UNLOGGED = True

    route_key = models.BinaryField(primary_key=True)
    channel_group = models.TextField()
    # Routing fields only; the two socket values are stored separately so new
    # browser sessions do not create new summary rows for the same audience.
    payload = models.JSONField()
    target_user_ids = ArrayField(
        models.IntegerField(), default=list, db_default=[], editable=False
    )
    all_users = models.BooleanField(default=False, db_default=False, editable=False)
    latest_event_id = models.BigIntegerField()
    latest_socket_id = models.TextField(null=True)
    # The latest event with a different ignored socket. A null socket means the
    # event ignores nobody; only a null event ID means this second pair is absent.
    previous_event_id = models.BigIntegerField(null=True)
    previous_socket_id = models.TextField(null=True)

    class Meta:
        db_table = "ws_realtime_event_history_summary"
        # Keep changing maxima out of indexes so summary updates can use HOT.
        indexes = [
            models.Index(
                fields=["channel_group"], name="ws_history_summary_channel_idx"
            ),
            GinIndex(
                fields=["target_user_ids"],
                condition=models.Q(channel_group="users"),
                name="ws_history_summary_targets_idx",
            ),
            models.Index(
                fields=["all_users"],
                condition=models.Q(channel_group="users", all_users=True),
                name="ws_history_summary_all_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    previous_event_id__isnull=True, previous_socket_id__isnull=True
                )
                | (
                    models.Q(previous_event_id__isnull=False)
                    & models.Q(previous_event_id__lt=models.F("latest_event_id"))
                ),
                name="ws_history_previous_pair",
            )
        ]


class RealtimeEventHistoryState(models.Model):
    """Known history boundary and the high-water mark after full rows are removed."""

    UNLOGGED = True

    id = models.PositiveSmallIntegerField(primary_key=True, db_default=1)
    floor = models.BigIntegerField(db_default=0)
    compacted_event_id = models.BigIntegerField(db_default=0)

    class Meta:
        db_table = "ws_realtime_event_history_state"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="ws_history_state_singleton"
            )
        ]
