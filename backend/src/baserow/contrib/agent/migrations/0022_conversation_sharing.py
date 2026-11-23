import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0021_agentapplication_pending_tool_choices"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="agentconversation",
            name="shared",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="agentconversation",
            name="started_by_trigger",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="agentmessage",
            name="sender",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="agentconversation",
            name="owner_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="agent_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunSQL(
            [
                """
                UPDATE agent_agentconversation
                SET shared = TRUE, started_by_trigger = TRUE
                WHERE owner_user_id IS NULL
                """,
                """
                UPDATE agent_agentmessage AS m SET sender_id = c.owner_user_id
                FROM agent_agentconversation AS c
                WHERE m.conversation_id = c.id AND c.owner_user_id IS NOT NULL
                """,
            ],
            migrations.RunSQL.noop,
        ),
    ]
