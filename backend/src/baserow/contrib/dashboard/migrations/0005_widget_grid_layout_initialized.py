from django.db import migrations, models


def mark_existing_widget_grid_layouts_initialized(apps, schema_editor):
    Widget = apps.get_model("dashboard", "Widget")
    Widget.objects.update(grid_layout_initialized=True)


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0004_widget_grid_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="widget",
            name="grid_layout_initialized",
            field=models.BooleanField(db_default=False, default=True),
        ),
        migrations.RunPython(
            mark_existing_widget_grid_layouts_initialized,
            migrations.RunPython.noop,
        ),
    ]
