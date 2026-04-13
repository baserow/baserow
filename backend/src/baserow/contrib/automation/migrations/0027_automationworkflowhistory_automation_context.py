from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0026_alter_automationworkflow_unique_together"),
    ]

    operations = [
        migrations.AddField(
            model_name="automationworkflowhistory",
            name="automation_context",
            field=models.JSONField(
                blank=True,
                db_default=None,
                help_text=(
                    "Tracks the automation chain context (depth and workflow IDs) "
                    "to detect and prevent loops across Celery task boundaries."
                ),
                null=True,
            ),
        ),
    ]
