from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("builder", "0019_repeat_element_styling"),
    ]

    operations = [
        migrations.AddField(
            model_name="columnelement",
            name="layout_type",
            field=models.CharField(
                choices=[
                    ("auto", "Auto"),
                    ("1:2", "Ratio 1 2"),
                    ("2:1", "Ratio 2 1"),
                    ("1:1:2", "Ratio 1 1 2"),
                    ("2:1:1", "Ratio 2 1 1"),
                    ("custom", "Custom"),
                ],
                default="auto",
                help_text="The layout type determining column widths.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="columnelement",
            name="column_widths",
            field=models.JSONField(
                default=list,
                help_text="Custom width configuration for each column. Used when layout_type is 'custom'. Each item can be a number (pixels), 'auto', or 'dynamic'.",
            ),
        ),
    ]
