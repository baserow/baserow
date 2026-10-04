import django.db.models.deletion
from django.db import migrations, models

import baserow.core.formula.field


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0121_agent"),
        ("database", "0226_rowhistory_actor"),
        ("integrations", "0037_coreresponseservice_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="localbaserowintegration",
            name="authorized_agent",
            field=models.ForeignKey(
                blank=True,
                db_default=None,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="core.agent",
            ),
        ),
        migrations.CreateModel(
            name="LocalBaserowVectorSearch",
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
                    "max_results",
                    models.PositiveIntegerField(
                        db_default=5,
                        default=5,
                        help_text="The maximum number of rows returned.",
                    ),
                ),
                (
                    "search_query",
                    baserow.core.formula.field.FormulaField(
                        blank=True,
                        default="",
                        help_text="The text to search for.",
                        null=True,
                    ),
                ),
                (
                    "field",
                    models.ForeignKey(
                        help_text="The field with vector search enabled that is "
                        "searched.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="database.field",
                    ),
                ),
                (
                    "included_fields",
                    models.ManyToManyField(
                        help_text="The fields returned for every matching row. All "
                        "fields when empty.",
                        related_name="+",
                        to="database.field",
                    ),
                ),
                (
                    "table",
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="database.table",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("core.service",),
        ),
    ]
