from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("automation", "0043_wait_node_waiting_index")]

    operations = [
        migrations.AddField(
            model_name="automationworkflowhistory",
            name="triggered_by_user_type",
            field=models.CharField(max_length=8, null=True),
        ),
    ]
