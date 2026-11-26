from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0029_agent_channels"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentapplication",
            name="suggested_messages",
            field=models.JSONField(blank=True, db_default=[], default=list),
        ),
    ]
