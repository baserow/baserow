import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0110_totpusedcode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="twofactorauthprovidermodel",
                    name="user",
                    field=models.OneToOneField(
                        help_text="User that setup 2fa with this provider",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="two_factor_auth_provider",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
