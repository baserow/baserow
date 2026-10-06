import django.db.models.deletion
from django.db import migrations, models

import baserow.core.formula.field


def remove_workspace_search_tools(apps, schema_editor):
    """
    The built-in "workspace search" tool was dropped before release; rows of
    that type would make the tool registry raise for the agents holding them.
    """

    AgentTool = apps.get_model("baserow_enterprise", "AgentTool")
    AgentTool.objects.filter(type="workspace_search").delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "baserow_enterprise",
            "0069_agentapplication_agentchatchannel_agentchat_and_more",
        ),
        ("core", "0127_workspaceskill"),
        ("automation", "0039_coreresponseactionnode_and_more"),
        ("builder", "0080_builderworkflowaction_trashed_and_more"),
        ("database", "0226_rowhistory_actor"),
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
        migrations.RunPython(remove_workspace_search_tools, migrations.RunPython.noop),
        migrations.CreateModel(
            name="CoreRunAgentActionNode",
            fields=[
                (
                    "automationnode_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="automation.automationnode",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("automation.automationnode",),
        ),
        migrations.AddField(
            model_name="agentchat",
            name="parent_chat",
            field=models.ForeignKey(
                blank=True,
                db_default=None,
                default=None,
                help_text="The conversation whose agent started this one through a tool call, when another agent did.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="child_chats",
                to="baserow_enterprise.agentchat",
            ),
        ),
        migrations.AlterField(
            model_name="agentchat",
            name="source",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("trigger", "Trigger"),
                    ("setup", "Setup"),
                    ("channel", "Channel"),
                    ("service", "Service"),
                ],
                db_default="manual",
                default="manual",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="CoreRunAgentDatabaseWorkflowAction",
            fields=[
                (
                    "databaseworkflowaction_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="database.databaseworkflowaction",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        help_text="The service which this action is associated with.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="core.service",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("database.databaseworkflowaction",),
        ),
        migrations.CreateModel(
            name="CoreRunAgentService",
            fields=[
                (
                    "service_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="core.service",
                    ),
                ),
                (
                    "prompt",
                    baserow.core.formula.field.FormulaField(
                        blank=True,
                        default="",
                        help_text="The message that opens the conversation.",
                        null=True,
                    ),
                ),
                (
                    "wait_for_result",
                    models.BooleanField(
                        db_default=False,
                        default=False,
                        help_text="Whether to run the agent's turn before answering, so the agent's reply is part of the result. Otherwise the run is queued and only the conversation link is returned.",
                    ),
                ),
                (
                    "agent_application",
                    models.ForeignKey(
                        help_text="The agent application to start a conversation with.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="baserow_enterprise.agentapplication",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("core.service",),
        ),
        migrations.CreateModel(
            name="CoreRunAgentWorkflowAction",
            fields=[
                (
                    "builderworkflowaction_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="builder.builderworkflowaction",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        help_text="The service which this action is associated with.",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.service",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("builder.builderworkflowaction",),
        ),
    ]
