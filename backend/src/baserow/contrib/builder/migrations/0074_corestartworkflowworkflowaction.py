from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("builder", "0073_localbaserowcreaterowsworkflowaction"),
        ("integrations", "0031_corestartworkflowservice"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoreStartWorkflowWorkflowAction",
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
