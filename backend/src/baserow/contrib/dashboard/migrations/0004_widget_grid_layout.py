from django.db import migrations, models

BATCH_SIZE = 1_000


def populate_widget_grid_layout(apps, schema_editor):
    Widget = apps.get_model("dashboard", "Widget")

    widgets_to_update = []
    current_dashboard_id = None
    next_grid_y = 0

    for widget in (
        Widget.objects.select_related("content_type")
        .order_by("dashboard_id", "order", "id")
        .iterator(chunk_size=BATCH_SIZE)
    ):
        if widget.dashboard_id != current_dashboard_id:
            current_dashboard_id = widget.dashboard_id
            next_grid_y = 0

        grid_height = 4 if widget.content_type.model == "summarywidget" else 9
        widget.grid_x = 0
        widget.grid_y = next_grid_y
        widget.grid_width = 6
        widget.grid_height = grid_height
        next_grid_y += grid_height
        widgets_to_update.append(widget)

        if len(widgets_to_update) == BATCH_SIZE:
            Widget.objects.bulk_update(
                widgets_to_update,
                ["grid_x", "grid_y", "grid_width", "grid_height"],
                batch_size=BATCH_SIZE,
            )
            widgets_to_update.clear()

    if widgets_to_update:
        Widget.objects.bulk_update(
            widgets_to_update,
            ["grid_x", "grid_y", "grid_width", "grid_height"],
            batch_size=BATCH_SIZE,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0003_widget_dashboarddatasource_summarywidget"),
    ]

    operations = [
        migrations.AddField(
            model_name="widget",
            name="grid_x",
            field=models.PositiveIntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name="widget",
            name="grid_y",
            field=models.PositiveIntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name="widget",
            name="grid_width",
            field=models.PositiveIntegerField(db_default=6, default=6),
        ),
        migrations.AddField(
            model_name="widget",
            name="grid_height",
            field=models.PositiveIntegerField(db_default=9, default=9),
        ),
        migrations.RunPython(populate_widget_grid_layout, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="widget",
            options={"ordering": ("grid_y", "grid_x", "id")},
        ),
    ]
