from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0020_agent_web_fetch"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentapplication",
            name="pending_tool_choices",
            field=models.JSONField(blank=True, db_default=None, null=True),
        ),
    ]
