import django.db.models.deletion
from django.db import migrations, models

import baserow.core.formula.field


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0029_alter_automationworkflowhistory_original_workflow"),
        ("baserow_enterprise", "0061_core_code_service_action_node"),
        ("builder", "0070_corecsvfilereaderworkflowaction"),
        ("core", "0107_twofactorauthprovidermodel_totpauthprovidermodel_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoreXLSFileReaderActionNode",
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
        migrations.CreateModel(
            name="CoreXLSFileReaderService",
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
                    "file",
                    baserow.core.formula.field.FormulaField(
                        blank=True,
                        help_text="The XLS or XLSX file to read.",
                    ),
                ),
                (
                    "sheet_name",
                    baserow.core.formula.field.FormulaField(
                        blank=True,
                        help_text="The sheet to read. The first sheet is used when empty.",
                    ),
                ),
                (
                    "first_line_is_header",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "Whether the first line of the spreadsheet contains "
                            "column names."
                        ),
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("core.service",),
        ),
        migrations.CreateModel(
            name="CoreXLSFileReaderWorkflowAction",
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
