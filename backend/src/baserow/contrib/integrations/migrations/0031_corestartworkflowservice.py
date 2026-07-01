from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0031_localbaserowfieldsupdatedtriggernode"),
        ("integrations", "0030_localbaserowcreaterows"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoreManualTriggerService",
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
            ],
            bases=("core.service",),
        ),
        migrations.CreateModel(
            name="CoreStartWorkflowService",
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
                    "workflow",
                    models.ForeignKey(
                        help_text="The automation workflow to start.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="automation.automationworkflow",
                    ),
                ),
            ],
            bases=("core.service",),
        ),
    ]
