from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agent", "0019_clear_legacy_agent_run_as")]

    operations = [
        migrations.AddField(
            model_name="agentapplication",
            name="web_fetch_enabled",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="agentreplytranscript",
            name="paused_web_fetch",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
