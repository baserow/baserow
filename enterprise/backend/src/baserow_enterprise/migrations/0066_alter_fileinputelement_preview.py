from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_enterprise", "0065_remove_text_format_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fileinputelement",
            name="preview",
            field=models.BooleanField(
                default=True,
                help_text="Whether to show a preview of image files.",
            ),
        ),
    ]
