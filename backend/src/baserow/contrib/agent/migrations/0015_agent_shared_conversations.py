import django.db.models.deletion
from django.conf import settings
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("agent", "0014_agent_triggers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="agentconversation",
            name="owner_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="agent_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="agentmessage",
            name="role",
            field=models.CharField(
                choices=[
                    ("user", "User"),
                    ("assistant", "Assistant"),
                    ("trigger", "Trigger"),
                ],
                db_default="user",
                default="user",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="agentconversation",
            name="trigger",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conversations",
                to="agent.agenttrigger",
            ),
        ),
        AddIndexConcurrently(
            model_name="agentconversation",
            index=models.Index(
                fields=["agent", "-pinned", "-updated_on", "-id"],
                name="agent_conversation_shared_idx",
            ),
        ),
    ]
