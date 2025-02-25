import os
import tempfile
from pathlib import Path
from unittest.mock import call, patch

from django.db import connection, transaction

import pytest
from freezegun import freeze_time

from baserow.contrib.database.table.models import Table
from baserow.core.management.backup.backup_runner import BaserowBackupRunner
from baserow.core.management.backup.exceptions import InvalidBaserowBackupArchive
from baserow.core.psycopg import is_psycopg3
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db(transaction=True)
@pytest.mark.once_per_day_in_ci
def test_can_backup_and_restore_baserow_reverting_changes(data_fixture, environ):
    runner = BaserowBackupRunner(
        host=connection.settings_dict["HOST"],
        database=connection.settings_dict["NAME"],
        username=connection.settings_dict["USER"],
        port=connection.settings_dict["PORT"],
        jobs=1,
    )
    environ["PGPASSWORD"] = connection.settings_dict["PASSWORD"]

    table, fields, rows = data_fixture.build_table(
        columns=[
            ("Name", "text"),
        ],
        rows=[["A"], ["B"], ["C"], ["D"]],
    )
    table_to_delete, _, _ = data_fixture.build_table(
        columns=[
            ("Name", "text"),
        ],
        rows=[["A"], ["B"], ["C"], ["D"]],
    )
    deleted_table_name = table_to_delete.get_database_table_name()

    with tempfile.TemporaryDirectory() as temporary_directory_name:
        backup_loc = temporary_directory_name + "/backup.tar.gz"
        # With a batch size of 1 we expect 3 separate pg_dumps to be run.
        runner.backup_baserow(backup_loc, 1)
        assert Path(backup_loc).is_file()

        model = table.get_model(attribute_names=True)

        # Add a new row after we took the back-up that we want to reset by restoring.
        model.objects.create(**{"name": "E"})
        # Delete a table to check it is recreated.
        with transaction.atomic():
            TrashHandler.permanently_delete(table_to_delete)

        assert model.objects.count() == 5
        assert Table.objects.count() == 1
        assert deleted_table_name not in connection.introspection.table_names()

        # --clean will make pg_restore overwrite existing db objects, not safe for
        # general usage as it will not delete tables/relations created after the
        # backup.
        runner.restore_baserow(backup_loc, ["--clean", "--if-exists"])

        # The row we made after the backup has gone
        assert model.objects.count() == 4
        # The table we deleted has been restored
        assert Table.objects.count() == 2
        assert deleted_table_name in connection.introspection.table_names()


@patch("tempfile.TemporaryDirectory")
@patch("psycopg.connect" if is_psycopg3 else "psycopg2.connect")
@patch("subprocess.check_output")
def test_backup_baserow_dumps_database_in_batches(
    mock_check_output, mock_connect, mock_tempfile, fs, environ
):
    mock_pyscopg2_call_to_return(
        mock_connect,
        [("public.database_table_1",), ("public.database_relation_1",)],
    )

    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]

    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=1,
    )

    with freeze_time("2020-01-02 12:00"):
        runner.backup_baserow()

    assert os.path.exists(f"baserow_backup_{dbname}_2020-01-02_12-00-00.tar.gz")

    assert mock_check_output.call_count == 2
    mock_check_output.assert_has_calls(
        [
            call(
                [
                    "pg_dump",
                    f"--host={host}",
                    f"--dbname={dbname}",
                    f"--port={port}",
                    f"--username={user}",
                    "-Fd",
                    "--jobs=1",
                    "-w",
                    "--exclude-table=database_multiplecollaborators_*",
                    "--exclude-table=database_multipleselect_*",
                    "--exclude-table=database_table_*",
                    "--exclude-table=database_relation_*",
                    "--file=/fake_tmp_dir/everything_but_user_tables/",
                ]
            ),
            call(
                [
                    "pg_dump",
                    f"--host={host}",
                    f"--dbname={dbname}",
                    f"--port={port}",
                    f"--username={user}",
                    "-Fd",
                    "--jobs=1",
                    "-w",
                    "--table=public.database_table_1",
                    "--table=public.database_relation_1",
                    "--file=/fake_tmp_dir/user_tables_batch_0/",
                ],
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("psycopg.connect" if is_psycopg3 else "psycopg2.connect")
@patch("subprocess.check_output")
def test_can_change_num_jobs_and_insert_extra_args_for_baserow_backup(
    mock_check_output, mock_connect, mock_tempfile, fs, environ
):
    mock_pyscopg2_call_to_return(
        mock_connect,
        [
            ("public.database_table_1",),
            ("public.database_relation_1",),
            ("public.database_multipleselect_65",),
            ("public.database_multiplecollaborators_64",),
        ],
    )

    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]

    num_jobs = 5
    extra_arg = "--should_appear_in_all_pg_dump_calls"

    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=num_jobs,
    )

    with freeze_time("2020-01-02 12:00"):
        runner.backup_baserow(
            backup_file_name="test_backup.tar.gz",
            additional_pg_dump_args=[extra_arg],
        )

    assert os.path.exists("test_backup.tar.gz")

    assert mock_check_output.call_count == 2
    mock_check_output.assert_has_calls(
        [
            call(
                [
                    "pg_dump",
                    f"--host={host}",
                    f"--dbname={dbname}",
                    f"--port={port}",
                    f"--username={user}",
                    "-Fd",
                    f"--jobs={num_jobs}",
                    "-w",
                    "--exclude-table=database_multiplecollaborators_*",
                    "--exclude-table=database_multipleselect_*",
                    "--exclude-table=database_table_*",
                    "--exclude-table=database_relation_*",
                    "--file=/fake_tmp_dir/everything_but_user_tables/",
                    extra_arg,
                ]
            ),
            call(
                [
                    "pg_dump",
                    f"--host={host}",
                    f"--dbname={dbname}",
                    f"--port={port}",
                    f"--username={user}",
                    "-Fd",
                    f"--jobs={num_jobs}",
                    "-w",
                    "--table=public.database_table_1",
                    "--table=public.database_relation_1",
                    "--table=public.database_multipleselect_65",
                    "--table=public.database_multiplecollaborators_64",
                    "--file=/fake_tmp_dir/user_tables_batch_0/",
                    extra_arg,
                ],
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("psycopg.connect" if is_psycopg3 else "psycopg2.connect")
@patch("subprocess.check_output")
def test_backup_baserow_table_batches_includes_all_tables_when_final_batch_small(
    mock_check_output, mock_connect, mock_tempfile, fs, environ
):
    mock_pyscopg2_call_to_return(
        mock_connect,
        [
            ("public.database_table_1",),
            ("public.database_table_2",),
            ("public.database_table_3",),
            ("public.database_table_4",),
        ],
    )

    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]
    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=1,
    )

    with freeze_time("2020-01-02 12:00"):
        runner.backup_baserow(batch_size=3)

    assert mock_check_output.call_count == 3
    mock_check_output.assert_has_calls(
        [
            a_pg_dump_for_everything_else(),
            (
                a_pg_dump_table_batch(
                    tables=[
                        "public.database_table_1",
                        "public.database_table_2",
                        "public.database_table_3",
                    ],
                    batch_num=0,
                )
            ),
            (
                a_pg_dump_table_batch(
                    tables=[
                        "public.database_table_4",
                    ],
                    batch_num=1,
                )
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("psycopg.connect" if is_psycopg3 else "psycopg2.connect")
@patch("subprocess.check_output")
def test_backup_baserow_includes_all_tables_when_batch_size_matches_num_tables(
    mock_check_output, mock_connect, mock_tempfile, fs, environ
):
    tables_returned_by_sql = [
        ("public.database_table_1",),
        ("public.database_table_2",),
        ("public.database_table_3",),
    ]
    mock_pyscopg2_call_to_return(
        mock_connect,
        tables_returned_by_sql,
    )

    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]
    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=1,
    )

    with freeze_time("2020-01-02 12:00"):
        runner.backup_baserow(batch_size=len(tables_returned_by_sql))

    assert mock_check_output.call_count == 2
    mock_check_output.assert_has_calls(
        [
            a_pg_dump_for_everything_else(),
            (
                a_pg_dump_table_batch(
                    tables=[
                        "public.database_table_1",
                        "public.database_table_2",
                        "public.database_table_3",
                    ],
                    batch_num=0,
                )
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("psycopg.connect" if is_psycopg3 else "psycopg2.connect")
@patch("subprocess.check_output")
def test_backup_baserow_does_no_table_batches_when_no_user_tables_found(
    mock_check_output, mock_connect, mock_tempfile, fs, environ
):
    mock_pyscopg2_call_to_return(
        mock_connect,
        [],
    )

    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]
    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=1,
    )

    with freeze_time("2020-01-02 12:00"):
        runner.backup_baserow()

    assert mock_check_output.call_count == 1
    mock_check_output.assert_has_calls(
        [
            a_pg_dump_for_everything_else(),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("subprocess.check_output")
@patch("tarfile.open")
def test_restore_baserow_restores_contained_dumps_in_batches(
    mock_tarfile_open, mock_check_output, mock_tempfile, fs, environ
):
    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir/")
    fs.create_dir("/fake_tmp_dir/backup.tar.gz/everything_but_user_tables")
    fs.create_dir("/fake_tmp_dir/backup.tar.gz/user_tables_batch_0")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]

    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=1,
    )

    runner.restore_baserow("backup.tar.gz")

    assert mock_check_output.call_count == 2

    mock_check_output.assert_has_calls(
        [
            (
                call(
                    [
                        "pg_restore",
                        f"--host={host}",
                        f"--dbname={dbname}",
                        f"--port={port}",
                        f"--username={user}",
                        "-Fd",
                        "--jobs=1",
                        "-w",
                        "/fake_tmp_dir/backup.tar.gz/everything_but_user_tables/",
                    ]
                )
            ),
            (
                call(
                    [
                        "pg_restore",
                        f"--host={host}",
                        f"--dbname={dbname}",
                        f"--port={port}",
                        f"--username={user}",
                        "-Fd",
                        "--jobs=1",
                        "-w",
                        "/fake_tmp_dir/backup.tar.gz/user_tables_batch_0",
                    ]
                )
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("subprocess.check_output")
@patch("tarfile.open")
def test_restore_baserow_passes_extra_args_to_all_pg_restores_and_can_set_jobs(
    mock_tarfile_open, mock_check_output, mock_tempfile, fs, environ
):
    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir/")
    fs.create_dir("/fake_tmp_dir/backup.tar.gz/everything_but_user_tables")
    fs.create_dir("/fake_tmp_dir/backup.tar.gz/user_tables_batch_0")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]

    num_jobs = 5
    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=num_jobs,
    )

    extra_arg = "--extra-arg"
    runner.restore_baserow("backup.tar.gz", [extra_arg])

    assert mock_check_output.call_count == 2

    mock_check_output.assert_has_calls(
        [
            (
                call(
                    [
                        "pg_restore",
                        f"--host={host}",
                        f"--dbname={dbname}",
                        f"--port={port}",
                        f"--username={user}",
                        "-Fd",
                        f"--jobs={num_jobs}",
                        "-w",
                        "/fake_tmp_dir/backup.tar.gz/everything_but_user_tables/",
                        extra_arg,
                    ]
                )
            ),
            (
                call(
                    [
                        "pg_restore",
                        f"--host={host}",
                        f"--dbname={dbname}",
                        f"--port={port}",
                        f"--username={user}",
                        "-Fd",
                        f"--jobs={num_jobs}",
                        "-w",
                        "/fake_tmp_dir/backup.tar.gz/user_tables_batch_0",
                        extra_arg,
                    ]
                )
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("subprocess.check_output")
@patch("tarfile.open")
def test_restore_baserow_only_does_first_restore_if_no_user_tables(
    mock_tarfile_open, mock_check_output, mock_tempfile, fs, environ
):
    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir/")
    fs.create_dir("/fake_tmp_dir/backup.tar.gz/everything_but_user_tables")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]

    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=1,
    )

    runner.restore_baserow("backup.tar.gz")

    assert mock_check_output.call_count == 1

    mock_check_output.assert_has_calls(
        [
            (
                call(
                    [
                        "pg_restore",
                        f"--host={host}",
                        f"--dbname={dbname}",
                        f"--port={port}",
                        f"--username={user}",
                        "-Fd",
                        "--jobs=1",
                        "-w",
                        "/fake_tmp_dir/backup.tar.gz/everything_but_user_tables/",
                    ]
                )
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("subprocess.check_output")
@patch("tarfile.open")
def test_restore_baserow_raises_exception_if_sub_folder_not_found_after_extract(
    mock_tarfile_open, mock_check_output, mock_tempfile, fs, environ
):
    mock_tempdir_to_be(fs, mock_tempfile, "/fake_tmp_dir/")
    fs.create_dir("/fake_tmp_dir/some_other_bad_folder/")

    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]

    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=user,
        port=port,
        jobs=1,
    )

    with pytest.raises(InvalidBaserowBackupArchive):
        runner.restore_baserow("backup.tar.gz")

    mock_check_output.assert_not_called()


def a_pg_dump_for_everything_else():
    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]

    return call(
        [
            "pg_dump",
            f"--host={host}",
            f"--dbname={dbname}",
            f"--port={port}",
            f"--username={user}",
            "-Fd",
            "--jobs=1",
            "-w",
            "--exclude-table=database_multiplecollaborators_*",
            "--exclude-table=database_multipleselect_*",
            "--exclude-table=database_table_*",
            "--exclude-table=database_relation_*",
            "--file=/fake_tmp_dir/everything_but_user_tables/",
        ]
    )


def a_pg_dump_table_batch(tables, batch_num):
    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]

    return call(
        [
            "pg_dump",
            f"--host={host}",
            f"--dbname={dbname}",
            f"--port={port}",
            f"--username={user}",
            "-Fd",
            "--jobs=1",
            "-w",
        ]
        + [f"--table={t}" for t in tables]
        + [
            f"--file=/fake_tmp_dir/user_tables_batch_{batch_num}/",
        ],
    )


def mock_tempdir_to_be(fs, mock_tempfile, dir_name):
    fs.create_dir(dir_name)
    mock_tempfile.return_value.__enter__.return_value = dir_name


def mock_pyscopg2_call_to_return(mock_connect, results):
    with mock_connect() as conn:
        with conn.cursor() as cursor:
            cursor.fetchall.return_value = results
