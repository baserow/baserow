from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0008_text_filter_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="textfilterwidget",
            name="input_format",
            field=models.CharField(
                choices=[("text", "Text"), ("number", "Number")],
                db_default="text",
                default="text",
                max_length=16,
            ),
        ),
    ]
