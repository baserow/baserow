from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0207_fix_data_sync_missing_primary_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="gridview",
            name="frozen_column_count",
            field=models.PositiveSmallIntegerField(
                default=1,
                db_default=1,
            ),
        ),
    ]
