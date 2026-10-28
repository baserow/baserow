from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("builder", "0080_builderworkflowaction_trashed_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="iframeelement",
            name="auto_height",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="Automatically resize embedded HTML to fit its content.",
            ),
        ),
    ]
