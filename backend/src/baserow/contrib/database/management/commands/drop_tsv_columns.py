from django.core.management.base import BaseCommand
from django.db import connection

from baserow.contrib.database.table.constants import (
    TSV_FIELD_PREFIX,
    USER_TABLE_DATABASE_NAME_PREFIX,
)


class Command(BaseCommand):
    help = (
        "Drops leftover tsv_field_* columns (and their indexes) from database_table_* "
        "tables. These columns are remnants of the old full-text search system that "
        "has since been replaced."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of tables to process per batch (default: 50).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would be dropped without making any changes.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN mode: no changes will be made.")
            )

        self.stdout.write("Scanning for leftover TSV columns...")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name LIKE %s
                  AND column_name LIKE %s
                ORDER BY table_name, column_name
                """,
                [
                    f"{USER_TABLE_DATABASE_NAME_PREFIX}%",
                    f"{TSV_FIELD_PREFIX}_%",
                ],
            )
            rows = cursor.fetchall()

        if not rows:
            self.stdout.write(
                self.style.SUCCESS("No leftover TSV columns found. Nothing to do.")
            )
            return

        tables: dict[str, list[str]] = {}
        for table_name, column_name in rows:
            tables.setdefault(table_name, []).append(column_name)

        total_tables = len(tables)
        total_columns = len(rows)
        self.stdout.write(
            f"Found {total_columns} TSV column(s) across {total_tables} table(s)."
        )

        if not dry_run:
            confirm = input("Type Y to drop them, or anything else to abort: ")
            if confirm.strip().upper() != "Y":
                self.stdout.write(self.style.WARNING("Aborted. No changes were made."))
                return

        table_items = list(tables.items())
        total_batches = (total_tables + batch_size - 1) // batch_size
        total_dropped_columns = 0
        total_dropped_indexes = 0

        for batch_num, batch_start in enumerate(
            range(0, total_tables, batch_size), start=1
        ):
            batch = table_items[batch_start : batch_start + batch_size]
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"\nBatch {batch_num}/{total_batches}: "
                    f"processing {len(batch)} table(s)..."
                )
            )

            for table_name, column_names in batch:
                indexes = self._find_tsv_indexes(table_name)

                self.stdout.write(
                    f"  {table_name}: dropping {len(column_names)} column(s)"
                    + (f" and {len(indexes)} index(es)" if indexes else "")
                    + f" [{', '.join(column_names)}]"
                )

                if not dry_run:
                    for index_name in indexes:
                        self._drop_index(index_name)
                    self._drop_columns(table_name, column_names)

                total_dropped_columns += len(column_names)
                total_dropped_indexes += len(indexes)

        action = "Would drop" if dry_run else "Dropped"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! {action} {total_dropped_columns} column(s) and "
                f"{total_dropped_indexes} index(es) across {total_tables} table(s)."
            )
        )

    def _find_tsv_indexes(self, table_name: str) -> list[str]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = current_schema()
                  AND tablename = %s
                  AND indexname LIKE 'tbl_tsv_%%_idx'
                """,
                [table_name],
            )
            return [row[0] for row in cursor.fetchall()]

    def _drop_index(self, index_name: str) -> None:
        with connection.cursor() as cursor:
            cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')

    def _drop_columns(self, table_name: str, column_names: list[str]) -> None:
        drop_clauses = ", ".join(
            f'DROP COLUMN IF EXISTS "{col}"' for col in column_names
        )
        with connection.cursor() as cursor:
            cursor.execute(f'ALTER TABLE "{table_name}" {drop_clauses}')
