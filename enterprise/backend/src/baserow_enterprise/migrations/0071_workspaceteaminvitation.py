import django.db.models.deletion
from django.db import migrations, models

import baserow.core.fields


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_enterprise", "0070_semantic_search"),
        ("core", "0126_alter_aiproviderconfig_api_key_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceTeamInvitation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", baserow.core.fields.SyncedDateTimeField(auto_now=True)),
                (
                    "invitation",
                    models.ForeignKey(
                        help_text="The workspace invitation that adds the person to "
                        "the team once accepted.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="team_invitations",
                        to="core.workspaceinvitation",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        help_text="The team the person joins once the invitation is "
                        "accepted.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitations",
                        to="baserow_enterprise.team",
                    ),
                ),
            ],
            options={
                "ordering": ("id",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("invitation", "team"),
                        name="team_invitation_team_uniqueness",
                    )
                ],
            },
        ),
    ]
