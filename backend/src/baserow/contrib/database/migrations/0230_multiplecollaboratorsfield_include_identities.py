from django.db import migrations, models


class Migration(migrations.Migration):
    replaces = [("database", "0230_identities_in_collaborator_and_long_text_fields")]
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
    ]
