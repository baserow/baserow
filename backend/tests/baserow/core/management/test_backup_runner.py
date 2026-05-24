import os
import tempfile
from pathlib import Path
from unittest.mock import call, patch

from django.db import connection

import pytest
from freezegun import freeze_time

from baserow.core.management.backup.backup_runner import BaserowBackupRunner
from baserow.core.management.backup.exceptions import InvalidBaserowBackupArchive
from baserow.core.psycopg import is_psycopg3, psycopg
from baserow.test_utils.helpers import setup_interesting_test_table


@pytest.mark.django_db(transaction=True)
@pytest.mark.once_per_day_in_ci
def test_can_backup_and_restore_baserow_reverting_changes(
    data_fixture, environ, temporary_database
):
    host = connection.settings_dict["HOST"]
    dbname = connection.settings_dict["NAME"]
    username = connection.settings_dict["USER"]
    port = connection.settings_dict["PORT"]
    password = connection.settings_dict["PASSWORD"]
    environ["PGPASSWORD"] = password

    runner = BaserowBackupRunner(
        host=host,
        database=dbname,
        username=username,
        port=port,
        jobs=1,
    )

    table, _, _, _, context = setup_interesting_test_table(data_fixture)

    model = table.get_model()
    original_row_count = model.objects.count()
    user_table_name = table.get_database_table_name()

    with tempfile.TemporaryDirectory() as temporary_directory_name:
        backup_loc = temporary_directory_name + "/backup.tar.gz"
        runner.backup_baserow(backup_loc, batch_size=1)
        assert Path(backup_loc).is_file()

        restore_runner = BaserowBackupRunner(
            host=host,
            database=temporary_database,
            username=username,
            port=port,
            jobs=1,
        )
        restore_runner.restore_baserow(backup_loc)

        with psycopg.connect(
            host=host,
            port=port,
            dbname=temporary_database,
            user=username,
            password=password,
        ) as verify_conn:
            with verify_conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {user_table_name}")
                assert cur.fetchone()[0] == original_row_count

                autonumber_field_id = context["name_to_field_id"]["autonumber"]
                seq_name = f"field_{autonumber_field_id}_seq"
                cur.execute(f"SELECT last_value FROM {seq_name}")
                assert cur.fetchone()[0] > 0


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
    port = str(connection.settings_dict["PORT"])

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
                    "--exclude-table=field_*_seq",
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
    port = str(connection.settings_dict["PORT"])

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
                    "--exclude-table=field_*_seq",
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
    port = str(connection.settings_dict["PORT"])
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
    port = str(connection.settings_dict["PORT"])
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
    port = str(connection.settings_dict["PORT"])
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
    port = str(connection.settings_dict["PORT"])

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
    port = str(connection.settings_dict["PORT"])

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
    port = str(connection.settings_dict["PORT"])

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
    port = str(connection.settings_dict["PORT"])

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
    port = str(connection.settings_dict["PORT"])

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
            "--exclude-table=field_*_seq",
            "--file=/fake_tmp_dir/everything_but_user_tables/",
        ]
    )


def a_pg_dump_table_batch(tables, batch_num):
    dbname = connection.settings_dict["NAME"]
    host = connection.settings_dict["HOST"]
    user = connection.settings_dict["USER"]
    port = str(connection.settings_dict["PORT"])

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
