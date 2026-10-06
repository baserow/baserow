import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "baserow_enterprise",
            "0069_agentapplication_agentchatchannel_agentchat_and_more",
        ),
        ("core", "0127_workspaceskill"),
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
        migrations.AddField(
            model_name="agenttool",
            name="trashed",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="agenttrigger",
            name="trashed",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="agentchatchannel",
            name="trashed",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.CreateModel(
            name="AgentSkill",
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
                (
                    "mode",
                    models.CharField(
                        choices=[("always", "Always"), ("on_demand", "On demand")],
                        db_default="always",
                        default="always",
                        max_length=16,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(db_default=0, default=0),
                ),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_skills",
                        to="baserow_enterprise.agentdefinition",
                    ),
                ),
                (
                    "skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_skills",
                        to="core.workspaceskill",
                    ),
                ),
            ],
            options={
                "ordering": ("order", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("agent", "skill"), name="unique_agent_skill"
                    )
                ],
            },
        ),
    ]
