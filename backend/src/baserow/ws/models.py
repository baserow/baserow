from django.contrib.postgres.indexes import GinIndex
from django.db import models


class RealtimeEvent(models.Model):
    UNLOGGED = True

    id = models.BigAutoField(primary_key=True)
    channel_group = models.TextField()
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ws_realtime_events"
        indexes = [
            models.Index(
                fields=["channel_group", "id"],
                name="ws_realtime_channel_group_idx",
            ),
            # Supports ``payload @> {...}`` containment queries.
            # ``jsonb_path_ops`` is ~5x smaller and sufficient for ``@>`` only.
            GinIndex(
                fields=["payload"],
                opclasses=["jsonb_path_ops"],
                name="ws_realtime_payload_gin_idx",
            ),
        ]
