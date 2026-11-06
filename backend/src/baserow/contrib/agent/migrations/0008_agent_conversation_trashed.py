from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agent", "0007_agent_message_steps")]

    operations = [
        migrations.AddField(
            model_name="agentconversation",
            name="trashed",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
