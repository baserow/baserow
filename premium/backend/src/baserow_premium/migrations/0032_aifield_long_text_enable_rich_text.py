from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_premium", "0031_ai_field_scheduled_update"),
    ]

    operations = [
        migrations.AddField(
            model_name="aifield",
            name="long_text_enable_rich_text",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="Enable rich text formatting for the text output.",
            ),
        ),
    ]
