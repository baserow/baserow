from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0027_agent_ask_person"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentaction",
            name="type",
            field=models.CharField(max_length=255, null=True),
        ),
    ]
