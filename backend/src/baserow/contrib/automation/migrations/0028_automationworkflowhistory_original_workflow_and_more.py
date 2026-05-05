import django.db.models.deletion
from django.db import migrations, models


def backfill_original_workflow(apps, schema_editor):
    AutomationWorkflowHistory = apps.get_model(
        "automation", "AutomationWorkflowHistory"
    )
    AutomationWorkflowHistory.objects.filter(original_workflow__isnull=True).update(
        original_workflow_id=models.F("workflow_id")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0027_alter_automationnodehistory_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="automationworkflowhistory",
            name="original_workflow",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="workflow_histories",
                to="automation.automationworkflow",
            ),
        ),
        migrations.RunPython(
            backfill_original_workflow,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="automationworkflowhistory",
            name="workflow",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cloned_workflow_histories",
                to="automation.automationworkflow",
            ),
        ),
        migrations.AlterField(
            model_name='automationworkflow',
            name='state',
            field=models.CharField(choices=[('draft', 'Draft'), ('live', 'Live'), ('paused', 'Paused'), ('disabled', 'Disabled'), ('test_clone', 'Test Clone')], db_default='draft', default='draft', max_length=20),
        ),
    ]
