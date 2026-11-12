import django.db.models.deletion
from django.db import migrations, models

import baserow.core.fields
import baserow.core.formula.field


class Migration(migrations.Migration):
    dependencies = [
        ("agent", "0013_agent_conversation_pinned"),
        ("core", "0135_workspaceinvitationlink_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentTrigger",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", baserow.core.fields.SyncedDateTimeField(auto_now=True)),
                ("trashed", models.BooleanField(db_index=True, default=False)),
                (
                    "name",
                    models.CharField(
                        blank=True, db_default="", default="", max_length=75
                    ),
                ),
                ("enabled", models.BooleanField(db_default=True, default=True)),
                (
                    "message",
                    baserow.core.formula.field.FormulaField(
                        blank=True, db_default="", default="", null=True
                    ),
                ),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="triggers",
                        to="agent.agentapplication",
                    ),
                ),
                (
                    "service",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_trigger",
                        to="core.service",
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
            },
        ),
    ]
