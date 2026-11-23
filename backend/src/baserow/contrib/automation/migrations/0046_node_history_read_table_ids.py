from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0045_automationworkflowhistory_triggered_by_user_type"),
        ("core", "0143_service_sample_data_table_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="automationnodehistory",
            name="read_table_ids",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text="The IDs of the database tables the node and the nodes it "
                "read used when it was dispatched, so who may see its message and "
                "result is decided from them later. Null for entries written before "
                "it was kept.",
                null=True,
            ),
        ),
    ]
