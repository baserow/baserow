from django.db import migrations, models


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
        migrations.AddField(
            model_name="widget",
            name="grid_layout_initialized",
            field=models.BooleanField(db_default=False, default=True),
        ),
        migrations.AlterModelOptions(
            name="widget",
            options={"ordering": ("grid_y", "grid_x", "id")},
        ),
    ]
