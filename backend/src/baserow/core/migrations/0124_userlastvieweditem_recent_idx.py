from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    # The index is built without blocking the writes of the running application,
    # which happen on every page load.
    atomic = False

    dependencies = [
        ("core", "0123_userprofile_preferences"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="userlastvieweditem",
            index=models.Index(
                fields=["user", "-last_viewed", "-id"],
                name="lastviewed_user_recent_idx",
            ),
        ),
    ]
