from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("baserow_enterprise", "0082_website_widget_agent_channel")]

    operations = [
        migrations.AddField(
            model_name="assistantchat",
            name="editor_context",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
