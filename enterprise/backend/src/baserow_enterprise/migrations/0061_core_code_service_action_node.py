import django.db.models.deletion
from django.db import migrations, models

import baserow.core.formula.field


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0029_alter_automationworkflowhistory_original_workflow"),
        ("baserow_enterprise", "0060_datascan_whole_words_datascanresult_cell_value"),
        ("builder", "0068_alter_page_unique_together"),
        ("core", "0107_twofactorauthprovidermodel_totpauthprovidermodel_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoreCodeActionNode",
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
            name="CoreCodeService",
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
                    "code",
                    baserow.core.formula.field.FormulaField(
                        blank=True, help_text="The code to execute."
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("core.service",),
        ),
        migrations.CreateModel(
            name="CoreCodeWorkflowAction",
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
