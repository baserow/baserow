from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("builder", "0080_builderworkflowaction_trashed_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="choiceelement",
            name="show_search",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="Whether to show a search input in the choice dropdown.",
            ),
        ),
    ]
