from django.db import models


class RealtimeEvent(models.Model):
    UNLOGGED = True

    id = models.BigAutoField(primary_key=True)
    channel_group = models.CharField(max_length=255)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ws_realtime_events"
        indexes = [
            models.Index(
                fields=["channel_group", "id"],
                name="ws_realtime_channel_group_idx",
            ),
        ]
