from django.db import migrations, models


class Migration(migrations.Migration):
    """
    This migration handles a special case during the "group" to "workspace" rename.

    When `AuditLogEntry.group_id` is renamed to `workspace_id`, we *don't* want
    to re-create the index, which has `group_id` in its `fields`.

    Unfortunately setting the `Index`'s `name` to the original `name` doesn't work,
    as Django will still want to drop the index, rename the field, and then re-create
    the index afterwards.

    This migration accomplishes two tasks:

    1. In `database_operations` it handles the forwards/backwards migration to rename
       the `group_id` column to/from `workspace_id`.
    2. In `state_operations` we inform Django that the state is changing so that the
       index is dropped, the field is renamed, and the index is recreated with a `name`
       that matches the fields in `fields`.

    Related URL: https://code.djangoproject.com/ticket/23577
    """

    dependencies = [
        ("baserow_enterprise", "0015_alter_team_workspace"),
    ]

    forwards = """
        ALTER TABLE baserow_enterprise_auditlogentry
        RENAME COLUMN group_id TO workspace_id;
        ALTER TABLE baserow_enterprise_auditlogentry
        RENAME CONSTRAINT baserow_enterprise_auditlogentry_group_id_check TO
        baserow_enterprise_auditlogentry_workspace_id_check;
    """

    backwards = """
        ALTER TABLE baserow_enterprise_auditlogentry
        RENAME COLUMN workspace_id TO group_id;
        ALTER TABLE baserow_enterprise_auditlogentry
        RENAME CONSTRAINT baserow_enterprise_auditlogentry_workspace_id_check TO
        baserow_enterprise_auditlogentry_group_id_check;
    """

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=forwards,
                    reverse_sql=backwards,
                ),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="auditlogentry",
                    name="baserow_ent_action__8db5d6_idx",
                ),
                migrations.RenameField(
                    model_name="auditlogentry",
                    old_name="group_id",
                    new_name="workspace_id",
                ),
                migrations.AddIndex(
                    model_name="auditlogentry",
                    index=models.Index(
                        fields=[
                            "-action_timestamp",
                            "user_id",
                            "workspace_id",
                            "action_type",
                        ],
                        name="baserow_ent_action__ca13aa_idx",
                        # Note: the index name in PG will
                        # be `baserow_ent_action__8db5d6_idx`
                    ),
                ),
            ],
        ),
    ]
