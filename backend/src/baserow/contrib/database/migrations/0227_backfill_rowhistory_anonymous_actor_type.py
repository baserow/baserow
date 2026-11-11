from django.db import migrations, transaction


ROW_HISTORY_BACKFILL_BATCH_SIZE = 10_000


def set_anonymous_actor_type(apps, schema_editor):
    """Backfill anonymous actors in short, primary-key-ordered transactions."""

    RowHistory = apps.get_model("database", "RowHistory")
    database_alias = schema_editor.connection.alias
    last_id = 0

    while row_history_ids := list(
        RowHistory.objects.using(database_alias)
        .filter(id__gt=last_id, actor_id__isnull=True)
        .order_by("id")
        .values_list("id", flat=True)[:ROW_HISTORY_BACKFILL_BATCH_SIZE]
    ):
        with transaction.atomic(using=database_alias):
            RowHistory.objects.using(database_alias).filter(
                id__in=row_history_ids,
                actor_id__isnull=True,
            ).update(actor_type="anonymous")
        last_id = row_history_ids[-1]


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("database", "0226_rowhistory_actor"),
    ]

    operations = [
        migrations.RunPython(set_anonymous_actor_type, migrations.RunPython.noop),
    ]
