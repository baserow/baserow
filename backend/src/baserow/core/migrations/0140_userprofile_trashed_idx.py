from django.db import migrations, models

from baserow.core.migration_utils import RetryableAddIndexConcurrently


def create_missing_user_profiles(apps, schema_editor):
    db = schema_editor.connection.alias
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("core", "UserProfile")
    user_ids = (
        User._base_manager.using(db)
        .filter(profile__isnull=True)
        .values_list("id", flat=True)
    )
    UserProfile._base_manager.using(db).bulk_create(
        [UserProfile(user_id=user_id) for user_id in user_ids],
        batch_size=1000,
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    # The index is built without blocking writes to every user's profile.
    atomic = False

    dependencies = [
        ("core", "0139_user_identities"),
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
        # No user should lack a profile; this keeps any that does listed as a person.
        migrations.RunPython(create_missing_user_profiles, migrations.RunPython.noop),
    ]
