from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0015_agent_shared_conversations"),
    ]

    operations = [
        migrations.AddField(
            model_name="agenttrigger",
            name="on_overlap",
            field=models.CharField(
                choices=[
                    ("skip", "Skip"),
                    ("wait", "Wait for the previous run"),
                    ("parallel", "Run in parallel"),
                ],
                db_default="skip",
                default="skip",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="agenttrigger",
            name="last_fired_on",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agenttrigger",
            name="last_skipped_on",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agenttrigger",
            name="last_skipped_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("rate_limited", "Rate limited"),
                    ("agent_rate_limited", "Agent rate limited"),
                    ("previous_running", "Previous run still going"),
                    ("queue_full", "Queue full"),
                ],
                db_default="",
                default="",
                max_length=32,
            ),
        ),
        migrations.AddIndex(
            model_name="agentconversation",
            index=models.Index(
                condition=models.Q(("trigger__isnull", False)),
                fields=["trigger", "-created_on"],
                name="agent_conversation_trigger_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="agentmessage",
            index=models.Index(
                condition=models.Q(("status__in", ("queued", "running", "waiting"))),
                fields=["conversation"],
                name="agent_message_active_idx",
            ),
        ),
    ]
