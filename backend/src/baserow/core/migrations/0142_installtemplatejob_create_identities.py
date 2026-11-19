from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0141_ai_provider_excluded_workspaces"),
    ]

    operations = [
        migrations.AddField(
            model_name="installtemplatejob",
            name="create_identities",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="Whether an identity is created for each installed "
                "application that acts as one, with access to only the installed "
                "applications.",
            ),
        ),
    ]
