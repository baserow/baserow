from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0141_ai_provider_excluded_workspaces"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="sample_data_table_ids",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text="The IDs of the database tables the sample data was built "
                "from: the tables of the service and of what it read when the sample "
                "was stored. Null when it isn't known.",
                null=True,
            ),
        ),
    ]
