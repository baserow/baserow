from django.db import migrations, models

from baserow.core.migration_utils import RetryableAddIndexConcurrently


class Migration(migrations.Migration):
    # The index is built without blocking writes to every user's profile.
    atomic = False

    dependencies = [
        ("core", "0138_user_identities"),
    ]

    operations = [
        RetryableAddIndexConcurrently(
            model_name="userprofile",
            index=models.Index(
                condition=models.Q(("trashed", True)),
                fields=["user"],
                name="core_profile_trashed_idx",
            ),
        ),
    ]
