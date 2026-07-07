from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0033_localbaserowcreaterowsactionnode"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoreManualTriggerNode",
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
            name="CoreStartWorkflowActionNode",
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
    ]
