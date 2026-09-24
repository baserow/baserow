from django.db import migrations, models, transaction


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
    # Release the schema operations' ACCESS EXCLUSIVE locks before starting the
    # potentially long row-history backfill. Each backfill batch manages its own
    # short transaction in set_anonymous_actor_type.
    atomic = False

    dependencies = [
        ("database", "0223_gridview_group_by_layout"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="rowhistory",
                    name="user_name",
                    field=models.CharField(
                        blank=True,
                        help_text="The name of the user that performed the action.",
                        max_length=160,
                    ),
                ),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name="rowhistory",
                    old_name="user_id",
                    new_name="actor_id",
                ),
                migrations.AlterField(
                    model_name="rowhistory",
                    name="actor_id",
                    field=models.PositiveIntegerField(
                        db_column="user_id",
                        help_text="The ID of the actor that performed the action.",
                        null=True,
                    ),
                ),
                migrations.RenameField(
                    model_name="rowhistory",
                    old_name="user_name",
                    new_name="actor_name",
                ),
                migrations.AlterField(
                    model_name="rowhistory",
                    name="actor_name",
                    field=models.CharField(
                        blank=True,
                        db_column="user_name",
                        help_text="The name of the actor that performed the action.",
                        max_length=160,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="rowhistory",
            name="actor_type",
            field=models.CharField(db_default="auth.User", max_length=255),
        ),
        migrations.RunPython(set_anonymous_actor_type, migrations.RunPython.noop),
    ]
