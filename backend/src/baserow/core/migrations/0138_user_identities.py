from django.db import migrations, models

from baserow.core.migration_utils import LockTimeoutMigration, set_lock_timeout

def refuse_identity_rollback(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        set_lock_timeout(cursor, "2s")
        # Hold the guard through reverse DDL so a new identity cannot become a person.
        cursor.execute("LOCK TABLE core_userprofile IN ACCESS EXCLUSIVE MODE")
    Profile = apps.get_model("core", "UserProfile")
    if (
        Profile._base_manager.using(schema_editor.connection.alias)
        .filter(user_type="identity")
        .exists()
    ):
        raise RuntimeError(
            "Cannot remove user types while identities exist. "
            "Permanently delete identities before rolling back."
        )


class Migration(LockTimeoutMigration):
    atomic = True

    dependencies = [("core", "0137_mcpendpoint_rename_create_dashboards")]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="user_type",
            field=models.CharField(
                choices=[("human", "Human"), ("identity", "Identity")],
                db_default="human",
                default="human",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="trashed",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="last_active",
            field=models.DateTimeField(blank=True, db_default=None, null=True),
        ),
        # Old processes still query core_agent, e.g. in the workspace delete cascade.
        # TODO ZDM: drop core_agent in the next version.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    [
                        "DELETE FROM core_trashentry WHERE trash_item_type = 'agent'",
                        "DELETE FROM core_agent",
                    ],
                    migrations.RunSQL.noop,
                ),
            ],
            state_operations=[migrations.DeleteModel(name="Agent")],
        ),
        migrations.RunPython(migrations.RunPython.noop, refuse_identity_rollback),
    ]
