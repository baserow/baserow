from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agent", "0008_agent_conversation_trashed")]

    operations = [
        migrations.AddField(
            model_name="agentapplication",
            name="web_search_enabled",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
