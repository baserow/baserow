from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("automation", "0041_automationworkflow_untrusted_content")]

    operations = [
        migrations.AddField(
            model_name="automationworkflowhistory",
            name="triggered_by_identity_type",
            field=models.CharField(max_length=16, null=True),
        ),
    ]
