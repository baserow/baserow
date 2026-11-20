from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_enterprise", "0075_auditlogentry_actor_user_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="buildercustomcode",
            name="html",
            field=models.TextField(
                blank=True,
                db_default="",
                default="",
                help_text="Custom HTML for the document head.",
            ),
        ),
    ]
