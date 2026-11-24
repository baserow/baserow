from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0022_conversation_sharing"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentconversation",
            name="is_test",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="Whether Kuma started the conversation to test the Agent. "
                "Every tool that changes data, and every action, asks first in it.",
            ),
        ),
    ]
