import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("baserow_enterprise", "0062_core_xls_file_reader"),
        ("core", "0107_twofactorauthprovidermodel_totpauthprovidermodel_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApplicationUserOverLimit",
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
                (
                    "since",
                    models.DateTimeField(
                        help_text=(
                            "The moment the workspace was first detected to be over "
                            "its application user limit."
                        ),
                    ),
                ),
                (
                    "workspace",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="application_user_over_limit",
                        to="core.workspace",
                    ),
                ),
            ],
        ),
    ]
