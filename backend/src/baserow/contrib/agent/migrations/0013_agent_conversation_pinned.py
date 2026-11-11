from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("agent", "0012_agent_tool_approval_tool_key")]

    operations = [
        migrations.AddField(
            model_name="agentconversation",
            name="pinned",
            field=models.BooleanField(default=False, db_default=False),
        ),
        migrations.AlterModelOptions(
            name="agentconversation",
            options={"ordering": ("-pinned", "-updated_on", "-id")},
        ),
        AddIndexConcurrently(
            model_name="agentconversation",
            index=models.Index(
                fields=["agent", "owner_user", "-pinned", "-updated_on", "-id"],
                name="agent_conversation_pinned_idx",
            ),
        ),
    ]
