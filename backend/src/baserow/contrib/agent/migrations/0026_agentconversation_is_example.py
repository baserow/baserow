from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0025_conversation_participants"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentconversation",
            name="is_example",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="Whether the conversation came with an import or a template "
                "as an example. It belongs to nobody of this instance.",
            ),
        ),
    ]
