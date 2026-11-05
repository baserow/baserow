from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0135_createusertemplatejob_make_public"),
        ("core", "0135_workspaceinvitationlink_scope"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiproviderconfig",
            name="excluded_workspaces",
            field=models.ManyToManyField(
                blank=True,
                help_text="Workspaces that cannot use this instance-wide provider.",
                related_name="+",
                to="core.workspace",
            ),
        ),
    ]
