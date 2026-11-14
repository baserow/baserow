from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0017_agent_actions"),
    ]

    operations = [
        migrations.AddField(
            model_name="agenttrigger",
            name="batch_size",
            field=models.PositiveSmallIntegerField(db_default=20, default=20),
        ),
        migrations.AlterField(
            model_name="agenttrigger",
            name="last_skipped_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("rate_limited", "Rate limited"),
                    ("agent_rate_limited", "Agent rate limited"),
                    ("previous_running", "Previous run still going"),
                    ("queue_full", "Queue full"),
                    ("no_access", "No access"),
                    ("event_too_large", "Event too large"),
                ],
                db_default="",
                default="",
                max_length=32,
            ),
        ),
    ]
