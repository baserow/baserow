from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0025_conversation_participants"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentaction",
            name="type",
            field=models.CharField(max_length=255, null=True),
        ),
    ]
