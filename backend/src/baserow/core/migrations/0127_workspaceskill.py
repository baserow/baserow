import django.db.models.deletion

import baserow.core.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0126_alter_aiproviderconfig_api_key_max_length"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceSkill",
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
                (
                    "updated_on",
                    baserow.core.fields.SyncedDateTimeField(auto_now=True),
                ),
                ("name", models.CharField(max_length=160)),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        db_default="",
                        help_text=(
                            "One or two sentences on when an agent should use "
                            "the skill."
                        ),
                    ),
                ),
                (
                    "content",
                    models.TextField(
                        blank=True,
                        db_default="",
                        help_text="The markdown instructions.",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="skills",
                        to="core.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ("name", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("workspace", "name"),
                        name="unique_workspace_skill_name",
                    )
                ],
            },
        ),
    ]
