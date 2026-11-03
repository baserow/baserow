from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    # The index is built without blocking writes to every user's profile.
    atomic = False

    dependencies = [
        ("core", "0135_user_identities"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="userprofile",
            index=models.Index(
                condition=models.Q(("trashed", True)),
                fields=["user"],
                name="core_profile_trashed_idx",
            ),
        ),
    ]
