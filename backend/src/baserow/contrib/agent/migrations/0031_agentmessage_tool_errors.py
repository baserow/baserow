from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agent", "0030_agentapplication_suggested_messages")]

    operations = [
        migrations.AddField(
            model_name="agentmessage",
            name="tool_errors",
            field=models.JSONField(null=True),
        ),
    ]
