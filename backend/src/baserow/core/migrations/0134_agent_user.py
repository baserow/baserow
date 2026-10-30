import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q

from baserow.core.migration_utils import LockTimeoutMigration


def keep_new_user_ids_above_legacy_agent_ids(apps, schema_editor):
    """Keep new agent users above ids allocated by the old Agent sequence."""

    with schema_editor.connection.cursor() as cursor:
        # Match Agent creation's lock order and prevent a concurrent sequence rewind.
        cursor.execute("LOCK TABLE auth_user IN SHARE ROW EXCLUSIVE MODE")
        cursor.execute("LOCK TABLE core_agent IN SHARE ROW EXCLUSIVE MODE")
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM core_agent")
        max_agent_id = cursor.fetchone()[0]
        if max_agent_id == 0:
            return
        cursor.execute("SELECT pg_get_serial_sequence('auth_user', 'id')")
        sequence = cursor.fetchone()[0]
        cursor.execute(
            "SELECT setval(%s, GREATEST(nextval(%s), %s))",
            [sequence, sequence, max_agent_id],
        )


class Migration(LockTimeoutMigration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0133_template_shared_content"),
    ]

    operations = [
        migrations.RunPython(
            keep_new_user_ids_above_legacy_agent_ids, migrations.RunPython.noop
        ),
        migrations.AddField(
            model_name="agent",
            name="user",
            field=models.OneToOneField(
                help_text="The user this agent is stored as in user foreign keys. "
                "Its id is the agent's id.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agent",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="agent",
            constraint=models.CheckConstraint(
                condition=Q(user__isnull=True) | Q(user=F("id")),
                name="core_agent_id_is_user_id",
            ),
        ),
    ]
