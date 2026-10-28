from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0040_automationnode_max_retries_automationnode_on_failure_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="automationworkflow",
            name="untrusted_content",
            field=models.BooleanField(
                default=False,
                db_default=False,
                help_text="Blocks custom code nodes until explicitly trusted.",
            ),
        ),
        migrations.AddField(
            model_name="automationworkflow",
            name="import_report",
            field=models.JSONField(
                default=list,
                db_default=[],
                editable=False,
                help_text="Active content found during import, using the imported object IDs.",
            ),
        ),
    ]
