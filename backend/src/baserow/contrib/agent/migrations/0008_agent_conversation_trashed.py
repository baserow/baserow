from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agent", "0007_agent_message_steps")]

    operations = [
        migrations.AddField(
            model_name="agentconversation",
            name="trashed",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AlterModelOptions(
            name="agentconversation",
            options={"ordering": ("-updated_on", "-id")},
        ),
        migrations.RemoveIndex(
            model_name="agentconversation",
            name="agent_conversation_owner_idx",
        ),
        migrations.AddIndex(
            model_name="agentconversation",
            index=models.Index(
                fields=["agent", "owner_user", "-updated_on", "-id"],
                name="agent_conversation_owner_idx",
            ),
        ),
    ]
