import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0134_workspaceinvitationlink"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspaceinvitationlink",
            name="scope_id",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="The id of the object the link gives a role on.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="workspaceinvitationlink",
            name="scope_type",
            field=models.ForeignKey(
                blank=True,
                help_text="The type of the object the link gives a role on, if it "
                "targets an object of the workspace instead of the workspace itself.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="contenttypes.contenttype",
            ),
        ),
        migrations.AlterField(
            model_name="workspaceinvitationlink",
            name="permissions",
            field=models.CharField(
                default="MEMBER",
                help_text="The permissions that people get within the workspace when "
                "they join through the link, or on the scope of the link if it has "
                "one.",
                max_length=32,
            ),
        ),
    ]
