from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0206_rowhistory_database_ro_action__6ea699_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="gridview",
            name="frozen_column_count",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
            ),
        ),
    ]
