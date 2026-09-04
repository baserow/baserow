from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("database", "0219_button_field_smtp_email_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="gridview",
            name="group_by_layout",
            field=models.CharField(
                choices=[("banner", "Banner"), ("column", "Column")],
                db_default="banner",
                default="banner",
                max_length=10,
                help_text="How grouped rows are presented: banners above each group, "
                "or one column per group-by level beside the rows.",
            ),
        ),
    ]
