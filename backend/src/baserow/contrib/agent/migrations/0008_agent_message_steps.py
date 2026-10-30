from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agent", "0007_agent_allowed_tools")]

    operations = [
        migrations.AddField(
            model_name="agentmessage", name="steps", field=models.JSONField(null=True)
        ),
    ]
