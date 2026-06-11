from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand
from django.db import connection, connections

from baserow.contrib.database.table.constants import (
    TSV_FIELD_PREFIX,
    USER_TABLE_DATABASE_NAME_PREFIX,
)
from baserow.core.psycopg import sql


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
            "--workers",
            type=int,
            default=1,
            help="Number of tables to process in parallel (default: 1).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would be dropped without making any changes.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        workers = options["workers"]
        dry_run = options["dry_run"]

        if batch_size < 1:
            self.stdout.write(self.style.ERROR("--batch-size must be at least 1."))
            return

        if workers < 1:
            self.stdout.write(self.style.ERROR("--workers must be at least 1."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN mode: no changes will be made.")
            )

        self.stdout.write("Scanning for leftover TSV columns...")

        if not dry_run:
            self._check_writable_primary_connection()

        first_batch = self._fetch_table_batch(batch_size)

        if not first_batch:
            self.stdout.write(
                self.style.SUCCESS("No leftover TSV columns found. Nothing to do.")
            )
            return

        if dry_run:
            self._handle_dry_run(first_batch)
            return

        first_batch_columns = sum(len(column_names) for _, column_names in first_batch)

        self.stdout.write(
            f"Found at least {first_batch_columns} TSV column(s) "
            f"across {len(first_batch)} table(s) in the first batch."
        )
        self.stdout.write(f"Using {workers} worker(s).")

        confirm = input("Type Y to drop them, or anything else to abort: ")
        if confirm.strip().upper() != "Y":
            self.stdout.write(self.style.WARNING("Aborted. No changes were made."))
            return

        total_batches = 0
        total_tables = 0
        total_dropped_columns = 0
        batch = first_batch

        while batch:
            total_batches += 1
            batch_column_count = sum(len(column_names) for _, column_names in batch)

            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"\nFetched batch {total_batches}: {len(batch)} table(s), "
                    f"{batch_column_count} column(s)."
                )
            )

            dropped_tables, dropped_columns = self._drop_batch_in_parallel(
                batch=batch,
                workers=workers,
            )

            total_tables += dropped_tables
            total_dropped_columns += dropped_columns

            # Only the main thread fetches batches. Workers never fetch work, so
            # workers cannot conflict with each other when selecting tables.
            batch = self._fetch_table_batch(batch_size)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Dropped {total_dropped_columns} column(s) "
                f"across {total_tables} table(s) in {total_batches} batch(es)."
            )
        )

    def _check_writable_primary_connection(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_is_in_recovery()")
            if cursor.fetchone()[0]:
                raise RuntimeError(
                    "This command must be run against the primary database, "
                    "not a read replica."
                )

            cursor.execute("SET default_transaction_read_only = off")
            cursor.execute("SET transaction_read_only = off")

    def _handle_dry_run(self, batch: list[tuple[str, list[str]]]) -> None:
        total_columns = sum(len(column_names) for _, column_names in batch)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\nFetched dry-run batch: {len(batch)} table(s), "
                f"{total_columns} column(s)."
            )
        )

        for table_name, column_names in batch:
            self._write_table_action(
                table_name=table_name,
                column_names=column_names,
                action="would drop",
            )

        self.stdout.write(
            self.style.WARNING(
                "\nDry-run only shows the first batch because columns are not "
                "dropped, so repeatedly fetching would return the same batch."
            )
        )

    def _drop_batch_in_parallel(
        self,
        batch: list[tuple[str, list[str]]],
        workers: int,
    ) -> tuple[int, int]:
        dropped_tables = 0
        dropped_columns = 0

        # Ensure worker threads don't inherit/share the main thread connection.
        connections.close_all()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._drop_columns, table_name, column_names): (
                    table_name,
                    column_names,
                )
                for table_name, column_names in batch
            }

            for future in as_completed(futures):
                table_name, column_names = futures[future]

                # Re-raises any exception from the worker and stops the command.
                future.result()

                self._write_table_action(
                    table_name=table_name,
                    column_names=column_names,
                    action="dropped",
                )

                dropped_tables += 1
                dropped_columns += len(column_names)

        return dropped_tables, dropped_columns

    def _fetch_table_batch(self, batch_size: int) -> list[tuple[str, list[str]]]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH batch_tables AS (
                    SELECT c.oid, c.relname AS table_name
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = current_schema()
                      AND c.relkind = 'r'
                      AND c.relname LIKE %s
                      AND EXISTS (
                          SELECT 1
                          FROM pg_attribute a
                          WHERE a.attrelid = c.oid
                            AND a.attnum > 0
                            AND NOT a.attisdropped
                            AND a.attname LIKE %s
                      )
                    ORDER BY c.relname
                    LIMIT %s
                )
                SELECT
                    bt.table_name,
                    string_agg(a.attname, ',' ORDER BY a.attname) AS column_names
                FROM batch_tables bt
                JOIN pg_attribute a ON a.attrelid = bt.oid
                WHERE a.attnum > 0
                  AND NOT a.attisdropped
                  AND a.attname LIKE %s
                GROUP BY bt.table_name
                ORDER BY bt.table_name
                """,
                [
                    f"{USER_TABLE_DATABASE_NAME_PREFIX}%",
                    f"{TSV_FIELD_PREFIX}_%",
                    batch_size,
                    f"{TSV_FIELD_PREFIX}_%",
                ],
            )

            return [
                (table_name, column_names.split(","))
                for table_name, column_names in cursor.fetchall()
            ]

    def _write_table_action(
        self, table_name: str, column_names: list[str], action: str
    ) -> None:
        preview_column_count = 10
        preview = ", ".join(column_names[:preview_column_count])
        suffix = "..." if len(column_names) > preview_column_count else ""

        self.stdout.write(
            f"  {table_name}: {action} {len(column_names)} column(s) "
            f"[{preview}{suffix}]"
        )

    def _drop_columns(self, table_name: str, column_names: list[str]) -> None:
        # Dropping a column automatically drops any indexes that depend on it.
        query = sql.SQL("ALTER TABLE {table} {drop_clauses}").format(
            table=sql.Identifier(table_name),
            drop_clauses=sql.SQL(", ").join(
                sql.SQL("DROP COLUMN {column}").format(column=sql.Identifier(col))
                for col in column_names
            ),
        )

        # Each worker thread gets its own Django DB connection.
        with connections["default"].cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = off")
            cursor.execute("SET transaction_read_only = off")
            cursor.execute(query)
