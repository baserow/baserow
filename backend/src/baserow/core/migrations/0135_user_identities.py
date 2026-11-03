import json

from django.db import migrations, models

from baserow.core.migration_utils import LockTimeoutMigration, set_lock_timeout

LEGACY_TYPED_REFERENCES = (
    (
        "database_localbaserowintegration",
        "authorized_subject_type",
        "Local Baserow authorizations",
    ),
    ("database_rowhistory", "actor_type", "row history"),
    ("automation_automationworkflowhistory", "triggered_by_type", "automation history"),
    ("baserow_enterprise_auditlogentry", "actor_type", "audit history"),
    (
        "baserow_enterprise_auditlogexportjob",
        "filter_actor_type",
        "audit export filters",
    ),
)


def contains_agent_subject(value):
    if isinstance(value, list):
        return any(contains_agent_subject(item) for item in value)
    if not isinstance(value, dict):
        return False
    subject_keys = {
        "subject_type",
        "subject_type_name",
        "authorized_subject_type",
        "subject_type_natural_key",
        "subject_subject_type_natural_key",
    }
    return any(
        (key in subject_keys and item in ("core.Agent", ["core", "agent"]))
        or contains_agent_subject(item)
        for key, item in value.items()
    )


def refuse_legacy_agents(apps, schema_editor):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    found = []
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        # Stop old Agent writes before checking the data that the table drop removes.
        cursor.execute("LOCK TABLE core_agent IN ACCESS EXCLUSIVE MODE")
        cursor.execute("SELECT EXISTS(SELECT 1 FROM core_agent)")
        if cursor.fetchone()[0]:
            found.append("Agent rows")
        for table, column, label in LEGACY_TYPED_REFERENCES:
            if table not in tables:
                continue
            columns = {
                field.name
                for field in connection.introspection.get_table_description(
                    cursor, table
                )
            }
            if column not in columns:
                continue
            cursor.execute(
                f"SELECT EXISTS(SELECT 1 FROM {quote(table)} WHERE {quote(column)} = %s)",  # noqa: S608
                ["core.Agent"],
            )
            if cursor.fetchone()[0]:
                found.append(label)
        for table in (
            "baserow_enterprise_roleassignment",
            "baserow_enterprise_teamsubject",
        ):
            if table not in tables:
                continue
            cursor.execute(
                f"SELECT EXISTS(SELECT 1 FROM {quote(table)} refs "  # noqa: S608
                "JOIN django_content_type ct ON ct.id = refs.subject_type_id "
                "WHERE ct.app_label = 'core' AND ct.model = 'agent')"
            )
            if cursor.fetchone()[0]:
                found.append(table)
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM core_trashentry WHERE trash_item_type = 'agent')"
        )
        if cursor.fetchone()[0]:
            found.append("Agent trash entries")
        cursor.execute(
            "SELECT params FROM core_action WHERE type IN "
            "('batch_assign_role', 'create_team', 'update_team', 'delete_team', "
            "'create_team_subject', 'delete_team_subject') "
            "AND (params::text LIKE %s OR params::text LIKE %s)",
            ["%core.Agent%", '%"agent"%'],
        )
        for (params,) in cursor:
            if isinstance(params, str):
                params = json.loads(params)
            if contains_agent_subject(params):
                found.append("role/team action parameters")
                break
    if found:
        raise RuntimeError(
            "Cannot replace legacy Agent identities: " + ", ".join(found) + ". "
            "Remove or explicitly migrate this nonproduction data before retrying. "
            "No Agent IDs have been reinterpreted or deleted."
        )


def refuse_identity_rollback(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        set_lock_timeout(cursor, "2s")
        # Hold the guard through reverse DDL so a new agent cannot become a person.
        cursor.execute("LOCK TABLE core_userprofile IN ACCESS EXCLUSIVE MODE")
    Profile = apps.get_model("core", "UserProfile")
    if (
        Profile._base_manager.using(schema_editor.connection.alias)
        .filter(identity_type="agent")
        .exists()
    ):
        raise RuntimeError(
            "Cannot remove identity types while agent Users exist. "
            "Permanently delete agent identities before rolling back."
        )


class Migration(LockTimeoutMigration):
    atomic = True

    dependencies = [("core", "0134_downloadusertemplatejob")]

    operations = [
        migrations.RunPython(refuse_legacy_agents, migrations.RunPython.noop),
        migrations.AddField(
            model_name="userprofile",
            name="identity_type",
            field=models.CharField(
                choices=[("human", "Human"), ("agent", "Agent")],
                db_default="human",
                default="human",
                max_length=5,
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
        migrations.DeleteModel(name="Agent"),
        migrations.RunPython(migrations.RunPython.noop, refuse_identity_rollback),
    ]
