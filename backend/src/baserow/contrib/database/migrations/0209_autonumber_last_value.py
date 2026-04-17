import logging
import time
from collections import defaultdict

from django.db import OperationalError, ProgrammingError, connection, migrations, models

from baserow.core.psycopg import sql

logger = logging.getLogger(__name__)


def populate_counters(apps, schema_editor):
    AutonumberField = apps.get_model("database", "AutonumberField")

    total = AutonumberField.objects.filter(field_ptr__trashed=False).count()
    if total == 0:
        return

    logger.info("Migrating %d autonumber fields to counter-based design.", total)
    start_time = time.monotonic()

    fields_by_table = defaultdict(list)
    autonumber_fields = (
        AutonumberField.objects.select_related("field_ptr__table")
        .filter(field_ptr__trashed=False)
        .iterator(chunk_size=500)
    )

    skipped = 0
    for autonumber in autonumber_fields:
        field_ptr = autonumber.field_ptr
        if field_ptr is None or field_ptr.table_id is None:
            logger.warning("Field %s or its table not found, skipping.", autonumber.pk)
            skipped += 1
            continue

        field_id = field_ptr.pk
        db_table = f"database_table_{field_ptr.table_id}"
        db_column = f"field_{field_id}"
        fields_by_table[db_table].append((autonumber, field_id, db_column))

    migrated = 0
    tables_processed = 0
    total_tables = len(fields_by_table)

    for db_table, fields in fields_by_table.items():
        try:
            _migrate_table_fields(db_table, fields)
            migrated += len(fields)
        except (ProgrammingError, OperationalError) as exc:
            logger.warning(
                "Could not process table %s (%d fields): %s. Skipping.",
                db_table,
                len(fields),
                exc,
            )
            skipped += len(fields)

        tables_processed += 1
        if tables_processed % 50 == 0 or tables_processed == total_tables:
            elapsed = time.monotonic() - start_time
            logger.info(
                "Progress: %d/%d tables, %d fields migrated, %d skipped (%.1fs elapsed).",
                tables_processed,
                total_tables,
                migrated,
                skipped,
                elapsed,
            )

    elapsed = time.monotonic() - start_time
    logger.info(
        "Autonumber counter migration complete: %d migrated, %d skipped in %.1fs.",
        migrated,
        skipped,
        elapsed,
    )


def _migrate_table_fields(db_table, fields):
    tbl = sql.Identifier(db_table)
    cols = [sql.Identifier(db_column) for _, _, db_column in fields]

    with connection.cursor() as cursor:
        # Check if any field still has a sequence default. If none do,
        # this table was already migrated (safe to skip on re-run).
        cursor.execute(
            "SELECT column_name, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = ANY(%s)",
            [db_table, [db_column for _, _, db_column in fields]],
        )
        defaults = {row[0]: row[1] for row in cursor.fetchall()}
        has_any_sequence = any(
            v and "nextval" in str(v) for v in defaults.values()
        )
        all_counters_set = all(
            autonumber.last_value >= 0 for autonumber, _, _ in fields
        )
        if not has_any_sequence and all_counters_set:
            return

        cursor.execute("SET statement_timeout = '300s'")
        try:
            max_exprs = sql.SQL(", ").join(
                sql.SQL("COALESCE(MAX({col}), 0)").format(col=c) for c in cols
            )
            cursor.execute(
                sql.SQL("SELECT {exprs} FROM {tbl}").format(exprs=max_exprs, tbl=tbl)
            )
            max_values = cursor.fetchone()
        finally:
            cursor.execute("RESET statement_timeout")

        for i, (autonumber, field_id, db_column) in enumerate(fields):
            col = cols[i]
            seq = sql.Identifier(f"{db_column}_seq")

            cursor.execute(
                "UPDATE database_autonumberfield "
                "SET last_value = GREATEST(last_value, %s) WHERE field_ptr_id = %s",
                [max_values[i], field_id],
            )

            default_val = defaults.get(db_column)
            if default_val and "nextval" in str(default_val):
                cursor.execute(
                    sql.SQL(
                        "ALTER TABLE {tbl} ALTER COLUMN {col} DROP DEFAULT"
                    ).format(tbl=tbl, col=col)
                )
            cursor.execute(sql.SQL("DROP SEQUENCE IF EXISTS {seq}").format(seq=seq))


def reverse_populate(apps, schema_editor):
    AutonumberField = apps.get_model("database", "AutonumberField")

    fields_by_table = defaultdict(list)
    autonumber_fields = (
        AutonumberField.objects.select_related("field_ptr__table")
        .filter(field_ptr__trashed=False)
        .iterator(chunk_size=500)
    )

    for autonumber in autonumber_fields:
        field_ptr = autonumber.field_ptr
        if field_ptr is None or field_ptr.table_id is None:
            continue

        field_id = field_ptr.pk
        db_table = f"database_table_{field_ptr.table_id}"
        db_column = f"field_{field_id}"
        fields_by_table[db_table].append((autonumber, field_id, db_column))

    for db_table, fields in fields_by_table.items():
        try:
            _reverse_table_fields(db_table, fields)
        except (ProgrammingError, OperationalError):
            logger.warning(
                "Could not reverse table %s, skipping.", db_table
            )


def _reverse_table_fields(db_table, fields):
    tbl = sql.Identifier(db_table)
    with connection.cursor() as cursor:
        for autonumber, _field_id, db_column in fields:
            col = sql.Identifier(db_column)
            seq = sql.Identifier(f"{db_column}_seq")
            last_value = autonumber.last_value or 0
            cursor.execute(
                sql.SQL("CREATE SEQUENCE IF NOT EXISTS {seq}").format(seq=seq)
            )
            if last_value > 0:
                cursor.execute(
                    sql.SQL("SELECT setval({seq_lit}, %s)").format(
                        seq_lit=sql.Literal(f"{db_column}_seq")
                    ),
                    [last_value],
                )
            cursor.execute(
                sql.SQL(
                    "ALTER TABLE {tbl} "
                    "ALTER COLUMN {col} "
                    "SET DEFAULT nextval({seq_lit})"
                ).format(tbl=tbl, col=col, seq_lit=sql.Literal(f"{db_column}_seq"))
            )
            cursor.execute(
                sql.SQL(
                    "ALTER SEQUENCE {seq} OWNED BY {tbl}.{col}"
                ).format(seq=seq, tbl=tbl, col=col)
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("database", "0208_gridview_frozen_column_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="autonumberfield",
            name="last_value",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="autonumberfield",
            name="is_unique_constraint_applied",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            populate_counters,
            reverse_populate,
        ),
    ]
