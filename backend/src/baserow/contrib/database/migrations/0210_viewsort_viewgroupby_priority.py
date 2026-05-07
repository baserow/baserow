from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0209_optimize_pending_search_value_update"),
    ]

    operations = [
        migrations.AddField(
            model_name="viewsort",
            name="priority",
            field=models.PositiveIntegerField(
                db_default=32767,
                default=32767,
                help_text="Position of this sorting in the ordering chain. The "
                "sorting with the lowest priority is applied first.",
            ),
        ),
        migrations.AddField(
            model_name="viewgroupby",
            name="priority",
            field=models.PositiveIntegerField(
                db_default=32767,
                default=32767,
                help_text="Position of this group by in the ordering chain. The "
                "group by with the lowest priority is applied first.",
            ),
        ),
        migrations.AlterModelOptions(
            name="viewsort",
            options={"ordering": ("priority", "id")},
        ),
        migrations.AlterModelOptions(
            name="viewgroupby",
            options={"ordering": ("priority", "id")},
        ),
    ]
