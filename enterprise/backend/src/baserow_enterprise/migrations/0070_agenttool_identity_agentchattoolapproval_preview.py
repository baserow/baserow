import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "baserow_enterprise",
            "0069_agentapplication_agentchatchannel_agentchat_and_more",
        ),
        ("core", "0121_agent"),
    ]

    operations = [
        migrations.AddField(
            model_name="agenttool",
            name="identity",
            field=models.ForeignKey(
                blank=True,
                db_default=None,
                default=None,
                help_text=(
                    "The workspace agent this tool acts as instead of the "
                    "application's identity."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="core.agent",
            ),
        ),
        migrations.AddField(
            model_name="agentchattoolapproval",
            name="preview",
            field=models.JSONField(
                blank=True,
                db_default=None,
                help_text=(
                    "A human-readable rendering of what the call will do "
                    "(resolved service fields, rows to write), built when the "
                    "approval is recorded."
                ),
                null=True,
            ),
        ),
    ]
