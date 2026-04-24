from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RealtimeEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                ("channel_group", models.CharField(max_length=255)),
                ("payload", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "ws_realtime_events",
                "indexes": [
                    models.Index(
                        fields=["channel_group", "id"],
                        name="ws_realtime_channel_group_idx",
                    ),
                    models.Index(
                        fields=["created_at"],
                        name="ws_rt_events_created_at_idx",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql="ALTER TABLE ws_realtime_events SET UNLOGGED;",
            reverse_sql="ALTER TABLE ws_realtime_events SET LOGGED;",
        ),
    ]
