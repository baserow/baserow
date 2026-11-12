from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("database", "0229_rowhistory_actor_user_type")]

    operations = [
        migrations.AddField(
            model_name="multiplecollaboratorsfield",
            name="include_identities",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text=(
                    "Indicates if the identities of the workspace can be assigned."
                ),
            ),
        ),
        migrations.AddField(
            model_name="longtextfield",
            name="long_text_include_identities",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text=(
                    "Indicates if the identities of the workspace can be mentioned."
                ),
            ),
        ),
    ]
