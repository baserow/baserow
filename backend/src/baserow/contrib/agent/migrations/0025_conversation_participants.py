from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0024_agentconversation_is_test"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="agentconversation",
            name="participants",
            field=models.ManyToManyField(
                related_name="participating_agent_conversations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="agentmessage",
            name="unattended",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.RunSQL(
            [
                """
                INSERT INTO agent_agentconversation_participants
                    (agentconversation_id, user_id)
                SELECT id, owner_user_id FROM agent_agentconversation
                WHERE owner_user_id IS NOT NULL
                """,
                """
                UPDATE agent_agentmessage AS m SET unattended = TRUE
                FROM agent_agentconversation AS c
                WHERE m.conversation_id = c.id AND c.started_by_trigger
                """,
            ],
            migrations.RunSQL.noop,
        ),
    ]
