from __future__ import print_function

from io import IOBase
from pathlib import Path

from django.core.management import call_command
from django.db import connections, transaction
from django.test.testcases import TransactionTestCase

import pytest

# noinspection PyUnresolvedReferences
from baserow.test_utils.pytest_conftest import *  # noqa: F403, F401

# Per physical database: a checksum of every table that holds rows right after a full
# flush, which are the tables the post_migrate signal fills (content types,
# permissions, ...). Lets `_fast_flush` keep those rows instead of recreating them.
_post_migrate_snapshots = {}


def _physical_database(connection):
    settings_dict = connection.settings_dict
    return settings_dict["HOST"], settings_dict["PORT"], settings_dict["NAME"]


def _list_tables(cursor):
    cursor.execute(
        """
        SELECT c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema() AND c.relkind = 'r'
            AND c.relname <> 'django_migrations'
        """
    )
    return [row[0] for row in cursor.fetchall()]


def _non_empty_tables(cursor, tables):
    if not tables:
        return []
    cursor.execute(
        " UNION ALL ".join(
            f'SELECT {index} WHERE EXISTS (SELECT 1 FROM "{table}")'
            for index, table in enumerate(tables)
        )
    )
    return [tables[row[0]] for row in cursor.fetchall()]


def _table_checksums(cursor, tables):
    if not tables:
        return {}
    cursor.execute(
        " UNION ALL ".join(
            f"SELECT {index}, md5(string_agg(t::text, ',' ORDER BY t::text)) "
            f'FROM "{table}" t'
            for index, table in enumerate(tables)
        )
    )
    return {tables[index]: checksum for index, checksum in cursor.fetchall()}


def _take_post_migrate_snapshot(connection):
    with connection.cursor() as cursor:
        tables = _non_empty_tables(cursor, _list_tables(cursor))
        return _table_checksums(cursor, tables)


def _fast_flush(connection, snapshot):
    """
    Empties the database the way a flush followed by post_migrate would, but
    deletes the rows of the few tables a test filled instead of truncating every
    table. TRUNCATE ... CASCADE reaches nearly every table through the user and
    content type tables, which makes it slow, and so does refilling the post_migrate
    tables afterwards.

    Returns False without changing anything if a test changed one of the
    post_migrate tables, in which case a full flush is needed.
    """

    with transaction.atomic(using=connection.alias), connection.cursor() as cursor:
        tables = _non_empty_tables(cursor, _list_tables(cursor))
        kept = [table for table in tables if table in snapshot]
        if _table_checksums(cursor, kept) != snapshot:
            return False
        emptied = [table for table in tables if table not in snapshot]
        # The rows can be deleted in any order because Django creates every foreign
        # key as DEFERRABLE INITIALLY DEFERRED: the constraints are only checked at
        # commit, when every table that still had rows has been emptied.
        for table in emptied:
            cursor.execute(f'DELETE FROM "{table}"')

    # Without this the deleted rows leave free space that new rows can be written
    # into out of order, which breaks tests relying on rows coming back in the order
    # they were created. VACUUM gives the tables back the empty pages a TRUNCATE
    # would leave.
    if emptied:
        with connection.cursor() as cursor:
            cursor.execute("VACUUM " + ", ".join(f'"{table}"' for table in emptied))
    return True


def _fixture_teardown(self):
    """
    This is a custom implementation of `TransactionTestCase._fixture_teardown`
    from Django (https://github.com/django/django/blob/main/django/test/testcases.py)
    that flushes test database after test runs with allow_cascade=True.

    This is needed as our custom Baserow tables won't be in the list of tables
    to truncate, and hence may create problems when rows are
    referencing other tables.

    Once a database has been fully flushed, later flushes go through `_fast_flush`.
    Aliases pointing at the same database (like `default-copy`) are flushed once.
    """

    flushed = set()
    for db_name in self._databases_names(include_mirrors=False):
        connection = connections[db_name]
        physical_database = _physical_database(connection)
        if physical_database in flushed:
            continue
        flushed.add(physical_database)

        # Allow TRUNCATE ... CASCADE and don't emit the post_migrate signal
        # when flushing only a subset of the apps
        inhibit_post_migrate = (
            self.available_apps is not None
            or (  # Inhibit the post_migrate signal when using serialized
                # rollback to avoid trying to recreate the serialized data.
                self.serialized_rollback
                and hasattr(connection, "_test_serialized_contents")
            )
        )
        snapshot = _post_migrate_snapshots.get(physical_database)
        if (
            not inhibit_post_migrate
            and snapshot is not None
            and _fast_flush(connection, snapshot)
        ):
            continue

        call_command(
            "flush",
            verbosity=0,
            interactive=False,
            database=db_name,
            reset_sequences=False,
            allow_cascade=True,  # CHANGED FROM DJANGO
            inhibit_post_migrate=inhibit_post_migrate,
        )
        if not inhibit_post_migrate:
            _post_migrate_snapshots[physical_database] = _take_post_migrate_snapshot(
                connection
            )


TransactionTestCase._fixture_teardown = _fixture_teardown


@pytest.fixture()
def test_data_dir() -> Path:
    """
    Returns root path for test data directory
    """

    return Path(__file__).parent.joinpath("test_data")


@pytest.fixture()
def open_test_file(test_data_dir):
    """
    Opens a test data file on a given path.

    usage:

    def test_me(open_test_file):
        with open_test_file('baserow/core/test.data', 'rt') as f:
            assert not f.closed

    Note: the caller can treat this as a context manager factory.
    """

    fhandle: IOBase | None = None

    def get_path(tpath, /, mode="rb") -> IOBase:
        nonlocal fhandle
        fhandle = (test_data_dir / (tpath)).open(mode=mode)

        return fhandle

    yield get_path
    if fhandle and not fhandle.closed:
        fhandle.close()


@pytest.fixture()
def on_db_connection(db):
    def register(callback):
        from django.db import connection

        callback(connection)

    yield register
