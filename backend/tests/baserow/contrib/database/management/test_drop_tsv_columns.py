from unittest.mock import patch

from django.core.management import call_command
from django.db import connection

import pytest

from baserow.contrib.database.table.constants import USER_TABLE_DATABASE_NAME_PREFIX


def _add_tsv_column(table_db_name: str, field_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f'ALTER TABLE "{table_db_name}" '
            f'ADD COLUMN IF NOT EXISTS "tsv_field_{field_id}" tsvector'
        )


def _add_tsv_index(table_db_name: str, field_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f'CREATE INDEX IF NOT EXISTS "tbl_tsv_{field_id}_idx" '
            f'ON "{table_db_name}" USING gin("tsv_field_{field_id}")'
        )


def _column_exists(table_db_name: str, column_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
            """,
            [table_db_name, column_name],
        )
        return cursor.fetchone() is not None


def _index_exists(index_name: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_indexes WHERE schemaname = current_schema() AND indexname = %s",
            [index_name],
        )
        return cursor.fetchone() is not None


@pytest.mark.django_db
def test_no_tsv_columns(data_fixture, capsys):
    call_command("drop_tsv_columns")

    captured = capsys.readouterr()
    assert "Nothing to do" in captured.out


# The command drops columns in worker threads that use their own database
# connections, so the test data must be committed for them to see it.
@pytest.mark.django_db(transaction=True)
def test_drops_columns_and_indexes(data_fixture, capsys):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    table_db_name = f"{USER_TABLE_DATABASE_NAME_PREFIX}{table.id}"

    _add_tsv_column(table_db_name, 101)
    _add_tsv_column(table_db_name, 102)
    _add_tsv_index(table_db_name, 101)
    _add_tsv_index(table_db_name, 102)

    assert _column_exists(table_db_name, "tsv_field_101")
    assert _column_exists(table_db_name, "tsv_field_102")
    assert _index_exists("tbl_tsv_101_idx")
    assert _index_exists("tbl_tsv_102_idx")

    with patch("builtins.input", return_value="Y"):
        call_command("drop_tsv_columns")

    assert not _column_exists(table_db_name, "tsv_field_101")
    assert not _column_exists(table_db_name, "tsv_field_102")
    assert not _index_exists("tbl_tsv_101_idx")
    assert not _index_exists("tbl_tsv_102_idx")

    captured = capsys.readouterr()
    assert table_db_name in captured.out
    assert "tsv_field_101" in captured.out
    assert "tsv_field_102" in captured.out
    assert "Dropped" in captured.out


@pytest.mark.django_db
def test_skips_other_tables(data_fixture, capsys):
    # Add a tsv_field_* column to a non-database_table table; it must be preserved.
    with connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE django_content_type "
            "ADD COLUMN IF NOT EXISTS tsv_field_999 tsvector"
        )

    call_command("drop_tsv_columns")

    assert _column_exists("django_content_type", "tsv_field_999")

    # Clean up after ourselves.
    with connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE django_content_type DROP COLUMN IF EXISTS tsv_field_999"
        )


@pytest.mark.django_db
def test_dry_run_does_not_drop(data_fixture, capsys):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    table_db_name = f"{USER_TABLE_DATABASE_NAME_PREFIX}{table.id}"

    _add_tsv_column(table_db_name, 201)
    _add_tsv_index(table_db_name, 201)

    call_command("drop_tsv_columns", dry_run=True)

    assert _column_exists(table_db_name, "tsv_field_201")
    assert _index_exists("tbl_tsv_201_idx")

    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "would drop" in captured.out


@pytest.mark.django_db
def test_abort_does_not_drop(data_fixture, capsys):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    table_db_name = f"{USER_TABLE_DATABASE_NAME_PREFIX}{table.id}"

    _add_tsv_column(table_db_name, 501)

    with patch("builtins.input", return_value="n"):
        call_command("drop_tsv_columns")

    assert _column_exists(table_db_name, "tsv_field_501")

    captured = capsys.readouterr()
    assert "Aborted" in captured.out


@pytest.mark.django_db(transaction=True)
def test_batch_size_one(data_fixture, capsys):
    user = data_fixture.create_user()
    tables = [data_fixture.create_database_table(user=user) for _ in range(3)]

    for i, table in enumerate(tables, start=301):
        table_db_name = f"{USER_TABLE_DATABASE_NAME_PREFIX}{table.id}"
        _add_tsv_column(table_db_name, i)

    with patch("builtins.input", return_value="Y"):
        call_command("drop_tsv_columns", batch_size=1)

    for i, table in enumerate(tables, start=301):
        table_db_name = f"{USER_TABLE_DATABASE_NAME_PREFIX}{table.id}"
        assert not _column_exists(table_db_name, f"tsv_field_{i}")

    captured = capsys.readouterr()
    # With batch_size=1 and 3 tables there should be 3 batch headers.
    assert "Fetched batch 1" in captured.out
    assert "Fetched batch 2" in captured.out
    assert "Fetched batch 3" in captured.out
    assert "3 batch(es)" in captured.out


@pytest.mark.django_db(transaction=True)
def test_output_reports_progress(data_fixture, capsys):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    table_db_name = f"{USER_TABLE_DATABASE_NAME_PREFIX}{table.id}"

    _add_tsv_column(table_db_name, 401)
    _add_tsv_column(table_db_name, 402)

    with patch("builtins.input", return_value="Y"):
        call_command("drop_tsv_columns")

    captured = capsys.readouterr()
    assert "Scanning" in captured.out
    assert "Found at least 2 TSV column(s)" in captured.out
    assert table_db_name in captured.out
    assert "tsv_field_401" in captured.out
    assert "tsv_field_402" in captured.out
    assert "Fetched batch 1" in captured.out
