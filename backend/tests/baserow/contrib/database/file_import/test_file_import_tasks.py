import json
from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple

from django.conf import settings
from django.test.utils import override_settings

import pytest
from freezegun import freeze_time
from pyinstrument import Profiler

from baserow.contrib.database.fields.dependencies.handler import FieldDependencyHandler
from baserow.contrib.database.fields.exceptions import IncompatibleField
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.field_constraints import (
    TextTypeUniqueWithEmptyConstraint,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import SelectOption, TextField
from baserow.contrib.database.rows.exceptions import InvalidRowLength
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.constants import (
    JOB_FAILED,
    JOB_FINISHED,
    JOB_PENDING,
    JOB_STARTED,
)
from baserow.core.jobs.models import Job
from baserow.core.jobs.tasks import clean_up_jobs, run_async_job


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task(data_fixture, patch_filefield_storage):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application()

    with patch_filefield_storage(), pytest.raises(UserNotInWorkspace):
        job = data_fixture.create_file_import_job(user=user, database=database)
        run_async_job(job.id)

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(data={"data": []})
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FAILED

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(data={"data": [[]]})
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FAILED

    with override_settings(INITIAL_TABLE_DATA_LIMIT=2), patch_filefield_storage():
        job = data_fixture.create_file_import_job(data={"data": [[], [], []]})
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FAILED

    with override_settings(MAX_FIELD_LIMIT=2), patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={"data": [["fields"] * 3, ["rows"] * 3]}
        )
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FAILED

    too_long_field_name = "x" * 256
    field_name_with_ok_length = "x" * 255

    data = [
        [too_long_field_name, "B", "C", "D"],
        ["1-1", "1-2", "1-3", "1-4", "1-5"],
        ["2-1", "2-2", "2-3"],
        ["3-1", "3-2"],
    ]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(data={"data": data})
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FAILED

    data[0][0] = field_name_with_ok_length
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(data={"data": data})
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FINISHED

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(data={"data": [["id"]]})
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FAILED

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(data={"data": [["test", "test"]]})
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FAILED

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(data={"data": [[" "]]})
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.state == JOB_FAILED

    # Basic use
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={
                "data": [
                    ["A", "B", "C", "D"],
                    ["1-1", "1-2", "1-3", "1-4", "1-5"],
                    ["2-1", "2-2", "2-3"],
                    ["3-1", "3-2"],
                ]
            }
        )
        run_async_job(job.id)

    job.refresh_from_db()

    table = job.table
    assert job.state == JOB_FINISHED
    assert job.progress_percentage == 100

    with pytest.raises(ValueError):
        # Check that the data file has been removed
        job.data_file.path

    text_fields = TextField.objects.filter(table=table)
    assert text_fields[0].name == "A"
    assert text_fields[1].name == "B"
    assert text_fields[2].name == "C"
    assert text_fields[3].name == "D"
    assert text_fields[4].name == "Field 5"

    model = table.get_model()
    rows = model.objects.all()

    assert len(rows) == 3

    # Without first row header
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={
                "data": [
                    ["1-1"],
                    ["2-1", "2-2", "2-3"],
                    ["3-1", "3-2"],
                ]
            },
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()

    table = job.table

    text_fields = TextField.objects.filter(table=table)
    assert text_fields[0].name == "Field 1"
    assert text_fields[1].name == "Field 2"
    assert text_fields[2].name == "Field 3"

    # Robust to strange field names
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={
                "data": [
                    [
                        "TEst 1",
                        "10.00",
                        'Falsea"""',
                        'a"a"a"a"a,',
                        "a",
                        1.3,
                        "/w. r/awr",
                    ],
                ]
            },
        )
        run_async_job(job.id)

    job.refresh_from_db()

    table = job.table
    text_fields = TextField.objects.filter(table=table)
    assert text_fields[0].name == "TEst 1"
    assert text_fields[1].name == "10.00"
    assert text_fields[2].name == 'Falsea"""'
    assert text_fields[3].name == 'a"a"a"a"a,'
    assert text_fields[4].name == "a"
    assert text_fields[5].name == "1.3"
    assert text_fields[6].name == "/w. r/awr"

    table = data_fixture.create_database_table(user=job.user)
    data_fixture.create_text_field(table=table, order=1, name="Name")
    data_fixture.create_number_field(
        table=table, order=2, name="Number 1", number_negative=True
    )
    data_fixture.create_created_on_field(table=table, order=2, name="Created_on")
    number_field = data_fixture.create_number_field(
        table=table,
        order=3,
        name="Number 2",
        number_negative=True,
        number_decimal_places=10,
    )
    data_fixture.create_text_field(table=table, order=4, name="Text 1")
    data_fixture.create_text_field(table=table, order=5, name="Text 2")

    model = table.get_model()

    # Import data to an existing table
    data = {"data": [["baz", 3, -3, "foo", None], ["bob", -4, 2.5, "bar", "a" * 255]]}

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=job.user, database=table.database, table=table, data=data
        )
        run_async_job(job.id)

    job.refresh_from_db()

    assert not job.report["failing_rows"]

    rows = model.objects.all()
    assert len(rows) == 2

    # Import data with different length
    data = {
        "data": [
            ["good", "test", "test", "Anything"],
            [],
            [None, None],
            ["good", 2.5, None, "Anything"],
            ["good", 2.5, None, "Anything", "too much", "values"],
        ]
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=job.user, database=table.database, table=table, data=data
        )
        run_async_job(job.id)

    job.refresh_from_db()

    rows = model.objects.all()
    assert len(rows) == 2 + 2

    assert sorted(job.report["failing_rows"].keys()) == ["0", "3", "4"]


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_for_special_fields(data_fixture, patch_filefield_storage):
    user = data_fixture.create_user()
    table, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    # number field updating another table through link & formula
    number_field = data_fixture.create_number_field(
        table=table_b, order=0, name="Number"
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        order=2,
        name="Number times two",
        formula=f"lookup('{link_field.name}', '{number_field.name}')*2",
        formula_type="number",
    )
    FieldDependencyHandler.rebuild_dependencies([formula_field], FieldCache())

    # single and multiple select fields
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table_b, order=3
    )
    multi_select_option_1 = SelectOption.objects.create(
        field=multiple_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    multi_select_option_2 = SelectOption.objects.create(
        field=multiple_select_field,
        order=2,
        value="Option 2",
        color="blue",
    )
    multiple_select_field.select_options.set(
        [multi_select_option_1, multi_select_option_2]
    )
    single_select_field = data_fixture.create_single_select_field(
        table=table_b, order=4
    )
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    single_select_option_2 = SelectOption.objects.create(
        field=single_select_field,
        order=2,
        value="Option 2",
        color="blue",
    )
    single_select_field.select_options.set(
        [single_select_option_1, single_select_option_2]
    )

    # file field
    file_field = data_fixture.create_file_field(table=table_b, order=5)
    file1 = data_fixture.create_user_file(
        original_name="test.txt",
        is_image=True,
    )
    file2 = data_fixture.create_user_file(
        original_name="test2.txt",
        is_image=True,
    )

    model = table.get_model()
    row_1 = model.objects.create()
    row_2 = model.objects.create()

    data = [
        [
            "one",
            10,
            [row_1.id],
            [multi_select_option_1.id],
            single_select_option_1.id,
            [{"name": file1.name, "visible_name": "new name"}],
        ],
        [
            "two",
            20,
            [row_2.id, row_1.id],
            [multi_select_option_1.id, multi_select_option_2.id],
            single_select_option_2.id,
            [{"name": file2.name, "visible_name": "another name"}],
        ],
        [
            "three",
            0,
            [],
            [],
            None,
            [],
        ],
    ]
    data = {"data": data}

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=user, database=table.database, table=table_b, data=data
        )
        run_async_job(job.id)

    job.refresh_from_db()

    model = table_b.get_model()

    rows = model.objects.all()
    assert len(rows) == 3

    data = [
        [
            "four",
            10,
            [0],
            [0],
            0,
            [{"name": "missing_file.txt", "visible_name": "new name"}],
        ],
        [
            "five",
            -1,
            [row_2.id, 0],
            [multi_select_option_1.id, 0],
            9999,
            [
                {},
                {"name": file2.name, "visible_name": "another name"},
                {"name": "missing_file.txt", "visible_name": "new name"},
            ],
        ],
        [
            "seven",
            10,
            [row_2.id],
            [multi_select_option_2.id],
            single_select_option_2.id,
            [
                {"name": file2.name, "visible_name": "another name"},
            ],
        ],
        [
            "six",
            1.2,
            [1.2, row_2.id],
            [1.3, multi_select_option_2.id],
            [],
            [
                {},
                {"name": file2.name, "visible_name": "another name"},
                {"name": "invalidValue", "visible_name": "new name"},
            ],
        ],
        [
            "seven",
            1,
            {"val": "bug"},
            {"val": "bug"},
            1.4,
            "bug",
        ],
    ]
    data = {"data": data}

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=user, database=table.database, table=table_b, data=data
        )
        run_async_job(job.id)

    job.refresh_from_db()

    rows = model.objects.all()
    assert len(rows) == 4

    assert sorted(job.report["failing_rows"].keys()) == ["0", "1", "3", "4"]

    assert sorted(job.report["failing_rows"]["0"].keys()) == sorted(
        [
            f"field_{multiple_select_field.id}",
            f"field_{single_select_field.id}",
            f"field_{file_field.id}",
        ]
    )

    assert sorted(job.report["failing_rows"]["1"].keys()) == sorted(
        [
            f"field_{number_field.id}",
            f"field_{file_field.id}",
        ]
    )

    assert sorted(job.report["failing_rows"]["3"].keys()) == sorted(
        [
            f"field_{number_field.id}",
            f"field_{link_field.id + 1}",
            f"field_{multiple_select_field.id}",
            f"field_{single_select_field.id}",
            f"field_{file_field.id}",
        ]
    )

    assert sorted(job.report["failing_rows"]["4"].keys()) == sorted(
        [
            f"field_{link_field.id + 1}",
            f"field_{multiple_select_field.id}",
            f"field_{single_select_field.id}",
            f"field_{file_field.id}",
        ]
    )


@pytest.mark.django_db(transaction=True)
def test_run_file_import_test_chunk(data_fixture, patch_filefield_storage):
    row_count = 1024 + 5

    user = data_fixture.create_user()

    table, _, _ = data_fixture.build_table(
        columns=[
            ("col1", "text"),
            ("col2", "number"),
        ],
        rows=[],
        user=user,
    )

    single_select_field = data_fixture.create_single_select_field(table=table, order=4)
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )
    single_select_option_2 = SelectOption.objects.create(
        field=single_select_field,
        order=2,
        value="Option 2",
        color="blue",
    )

    data = [["test", 1, single_select_option_1.id]] * row_count
    # 5 erroneous values
    data[5] = ["test", "bad", single_select_option_2.id]
    data[50] = ["test", "bad", 0]
    data[100] = ["test", "bad", ""]
    data[1024] = ["test", 2, 99999]
    data[1027] = ["test", "bad", single_select_option_2.id]

    print("data", len(data))
    data = {"data": data}

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(table=table, data=data, user=user)
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    assert not job.failed

    model = job.table.get_model()
    assert model.objects.count() == row_count - 5

    assert sorted(job.report["failing_rows"].keys()) == sorted(
        ["5", "50", "100", "1024", "1027"]
    )

    assert job.state == JOB_FINISHED
    assert job.progress_percentage == 100


@pytest.mark.django_db()
def test_run_file_import_limit(data_fixture, patch_filefield_storage):
    row_count = 2000
    max_error = settings.BASEROW_MAX_ROW_REPORT_ERROR_COUNT

    user = data_fixture.create_user()

    table, _, _ = data_fixture.build_table(
        columns=[
            ("col1", "text"),
            ("col2", "number"),
        ],
        rows=[],
        user=user,
    )

    single_select_field = data_fixture.create_single_select_field(table=table, order=4)
    single_select_option_1 = SelectOption.objects.create(
        field=single_select_field,
        order=1,
        value="Option 1",
        color="blue",
    )

    # Validation errors
    data = [["test", 1, single_select_option_1.id]] * row_count
    data += [["test", "bad", single_select_option_1.id]] * (max_error + 5)

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            table=table, data={"data": data}, user=user
        )

        run_async_job(job.id)

    job.refresh_from_db()

    model = job.table.get_model()
    assert model.objects.count() == 0

    assert job.state == JOB_FAILED
    assert job.error == "Too many errors"
    assert job.human_readable_error == "This file import has raised too many errors."

    assert len(job.report["failing_rows"]) == max_error

    # Row creation errors
    data = [["test", 1, single_select_option_1.id]] * row_count
    data += [["test", 1, 0]] * (max_error + 5)

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            table=table, data={"data": data}, user=user
        )
        run_async_job(job.id)

    job.refresh_from_db()

    assert model.objects.count() == 0

    assert job.state == JOB_FAILED
    assert job.error == "Too many errors"
    assert job.human_readable_error == "This file import has raised too many errors."

    assert (
        len(job.report["failing_rows"]) == settings.BASEROW_MAX_ROW_REPORT_ERROR_COUNT
    )

    assert len(job.report["failing_rows"]) == max_error


@pytest.mark.django_db(transaction=True)
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
# ~5 min (320s) on a 6 x i5-8400 CPU @ 2.80GHz (5599 bogomips)
def test_run_file_import_task_big_data(data_fixture, patch_filefield_storage):
    row_count = 100_000

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(column_count=100, row_count=row_count)

        profiler = Profiler()
        profiler.start()
        run_async_job(job.id)
        profiler.stop()

    job.refresh_from_db()

    model = job.table.get_model()
    assert model.objects.count() == row_count

    assert job.state == JOB_FINISHED
    assert job.progress_percentage == 100

    # A print we want to keep to show the performance statistics
    print(profiler.output_text(unicode=True, color=True, show_all=True))


@pytest.mark.django_db
def test_cleanup_file_import_job(data_fixture, settings, patch_filefield_storage):
    now = datetime.now(tz=timezone.utc)
    time_before_soft_limit = now - timedelta(
        minutes=settings.BASEROW_JOB_SOFT_TIME_LIMIT + 1
    )
    time_before_expiration = now - timedelta(
        minutes=settings.BASEROW_JOB_EXPIRATION_TIME_LIMIT + 1
    )
    # create recent job
    with freeze_time(now):
        job1 = data_fixture.create_file_import_job()

    with patch_filefield_storage() as storage:
        # Create old jobs
        with freeze_time(time_before_soft_limit):
            job1bis = data_fixture.create_file_import_job()
            job2 = data_fixture.create_file_import_job(state=JOB_STARTED)
            job3 = data_fixture.create_file_import_job(state=JOB_FINISHED)

        with freeze_time(time_before_expiration):
            job4 = data_fixture.create_file_import_job(state=JOB_FINISHED)
            job4_path = job4.data_file.path

        assert storage.exists(job4_path)

        with freeze_time(now):
            clean_up_jobs()

        # Check the file for job4 has been deleted
        assert not storage.exists(job4_path)

    assert Job.objects.count() == 4

    job1.refresh_from_db()
    assert job1.state == JOB_PENDING

    job1bis.refresh_from_db()
    assert job1.state == JOB_PENDING

    job2.refresh_from_db()
    assert job2.state == JOB_FAILED
    assert job2.updated_on == now

    job3.refresh_from_db()
    assert job3.state == JOB_FINISHED
    assert job3.updated_on == time_before_soft_limit


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert_fields_not_in_table(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=table, order=1, name="text 1")
    init_data = [["foo"], ["bar"]]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={
                "data": init_data,
                "configuration": {"upsert_fields": [100, 120]},
            },
            table=table,
            user=user,
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.failed
    assert job.error == "100"
    assert (
        job.human_readable_error
        == f"The provided field does not belong in the related table."
    )

    model = table.get_model()
    assert len(model.objects.all()) == 0


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert_fields_not_usable(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    f1 = data_fixture.create_text_field(table=table, order=1, name="text 1")
    f2 = data_fixture.create_formula_field(table=table, order=2, name="formula field")

    model = table.get_model()
    # dummy data just to ensure later on the table wasn't modified.
    init_data = [
        [
            "aa-",
        ],
        [
            "aa-",
        ],
    ]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={"data": init_data},
            table=table,
            user=user,
        )
        run_async_job(job.id)

    job.refresh_from_db()

    assert job.state == JOB_FINISHED
    assert job.progress_percentage == 100

    with pytest.raises(IncompatibleField):
        with patch_filefield_storage():
            job = data_fixture.create_file_import_job(
                data={
                    "data": [["bbb"], ["ccc"], ["aaa"]],
                    "configuration": {
                        # we're trying to use formula field, which is not supported
                        "upsert_fields": [f2.id],
                        "upsert_values": [["aaa"], ["aaa"], ["aaa"]],
                    },
                },
                table=table,
                user=user,
                first_row_header=False,
            )
            run_async_job(job.id)

    rows = model.objects.all()
    assert len(rows) == 2
    assert all([getattr(r, f1.db_column) == "aa-" for r in rows])


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert_fields_invalid_length(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    f1 = data_fixture.create_text_field(table=table, order=1, name="text 1")

    model = table.get_model()

    with pytest.raises(InvalidRowLength):
        with patch_filefield_storage():
            job = data_fixture.create_file_import_job(
                data={
                    "data": [["bbb"], ["ccc"], ["aaa"]],
                    "configuration": {
                        # fields and values have different lengths
                        "upsert_fields": [f1.id],
                        "upsert_values": [
                            ["aaa", "bbb"],
                        ],
                    },
                },
                table=table,
                user=user,
                first_row_header=False,
            )
            run_async_job(job.id)
    job.refresh_from_db()
    assert job.failed

    rows = model.objects.all()
    assert len(rows) == 0


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert(data_fixture, patch_filefield_storage):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)

    f1 = data_fixture.create_text_field(table=table, order=1, name="text 1")
    f2 = data_fixture.create_number_field(
        table=table, order=2, name="number 1", number_negative=True
    )
    f3 = data_fixture.create_date_field(user=user, table=table, order=3, name="date 1")
    f4 = data_fixture.create_date_field(
        user=user, table=table, order=4, name="datetime 1", date_include_time=True
    )
    f5 = data_fixture.create_number_field(
        table=table,
        order=5,
        name="value field",
        number_negative=True,
        number_decimal_places=10,
    )
    f6 = data_fixture.create_text_field(table=table, order=6, name="text 2")

    model = table.get_model()

    init_data = [
        [
            "aaa",
            1,
            "2024-01-01",
            "2024-01-01T01:02:03.004+01:00",
            0.1,
            "aaa-1-1",
        ],
        [
            "aab",
            1,
            "2024-01-01",
            "2024-01-01T01:02:03",
            0.2,
            "aab-1-1",
        ],
        [
            "aac",
            1,
            "2024-01-01",
            "2024-01-01T01:02:03",
            0.2,
            "aac-1-1",
        ],
        [
            None,
            None,
            None,
            None,
            None,
            None,
        ],
        [
            None,
            None,
            None,
            None,
            None,
            None,
        ],
        [
            "aac",
            1,
            None,
            "2024-01-01T01:02:03",
            0.2,
            "aac-1-2",
        ],
        [
            "aab",
            1,
            "2024-01-01",
            None,
            0.2,
            "aac-1-2",
        ],
        [
            "aaa",
            1,
            "2024-01-01",
            "2024-01-01T01:02:03.004+01:00",
            0.1,
            "aaa-1-1",
        ],
        [
            "aaa",
            1,
            "2024-01-02",
            "2024-01-01 01:02:03.004 +01:00",
            0.1,
            "aaa-1-1",
        ],
    ]

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={"data": init_data},
            table=table,
            user=user,
        )
        run_async_job(job.id)

    job.refresh_from_db()

    assert job.state == JOB_FINISHED
    assert job.progress_percentage == 100

    rows = model.objects.all()

    assert len(rows) == len(init_data)

    update_with_duplicates = [
        # first three are duplicates
        [
            "aab",
            1,
            "2024-01-01",
            "2024-01-01T01:02:03",
            0.3,
            "aab-1-1-modified",
        ],
        [
            "aaa",
            1,
            "2024-01-01",
            "2024-01-01T01:02:03.004+01:00",
            0.2,
            "aaa-1-1-modified",
        ],
        [
            "aab",
            1,
            "2024-01-01",
            None,
            0.33333,
            "aac-1-2-modified",
        ],
        # insert
        [
            "aab",
            1,
            None,
            None,
            125,
            "aab-1-3-new",
        ],
        [
            "aab",
            1,
            "2024-01-01",
            None,
            0.33333,
            "aab-1-4-new",
        ],
    ]
    # Without first row header
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={
                "data": update_with_duplicates,
                "configuration": {
                    "upsert_fields": [f1.id, f2.id, f3.id, f4.id],
                    "upsert_values": [i[:4] for i in update_with_duplicates],
                },
            },
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    assert not job.failed

    rows = list(model.objects.all())

    assert len(rows) == len(init_data) + 2

    last = rows[-1]
    assert getattr(last, f1.db_column) == "aab"
    assert getattr(last, f6.db_column) == "aab-1-4-new"

    last = rows[-2]
    assert getattr(last, f1.db_column) == "aab"
    assert getattr(last, f6.db_column) == "aab-1-3-new"


class UpsertData(NamedTuple):
    model: GeneratedTableModel
    text_field: TextField
    description: TextField


def prepare_upsert_data(
    data_fixture,
    patch_filefield_storage,
    open_test_file,
    upsert_field_idx: list[int],
    upsert_file_name: str | None,
) -> UpsertData:
    """
    Helper function to create test model + data for upsert functionality.


    :param data_fixture:
    :param patch_filefield_storage:
    :param open_test_file:
    :param upsert_field_idx: a list of indexes of fields from `upsert_fields` list
    :param upsert_file_name: file name part with test data for upsert functionality.
        Full file name is calculated, and should contain almost-full file import
        payload. Upsert fields configuration is updated in the code from
        `upsert_field_idx`.
    :return: UpsertData with context needed by upsert test
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)

    with open_test_file(
        "baserow/database/file_import/upsert_base_data_list.json", "rt"
    ) as f:
        init_data = json.load(f)

    upsert_fields = [
        data_fixture.create_text_field(table=table, name="Text"),
        data_fixture.create_long_text_field(table=table, name="Long text"),
        data_fixture.create_number_field(
            table=table, name="Number", number_decimal_places=3
        ),
        data_fixture.create_rating_field(table=table, name="Rating"),
        data_fixture.create_boolean_field(table=table, name="Boolean"),
        data_fixture.create_date_field(table=table, name="Date"),
        data_fixture.create_date_field(
            table=table, date_include_time=True, name="Datetime"
        ),
        data_fixture.create_duration_field(
            table=table, duration_format="d h", name="Duration"
        ),
        data_fixture.create_url_field(table=table, name="URL"),
        data_fixture.create_phone_number_field(table=table, name="Phone number"),
        data_fixture.create_email_field(table=table, name="Email"),
    ]
    text_field = upsert_fields[0]
    single_select = data_fixture.create_single_select_field(
        table=table, name="Single select"
    )
    for opt_value in ["aaa", "bbb", "ccc", "ddd"]:
        data_fixture.create_select_option(field=single_select, value=opt_value)
    description = data_fixture.create_long_text_field(table=table, name="Description")

    model = table.get_model()

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={"data": init_data[1:]},
            table=table,
            user=user,
        )
        run_async_job(job.id)
        job.refresh_from_db()
        assert job.finished

    assert len(model.objects.all()) == len(init_data) - 1

    upsert_fields = [upsert_fields[uidx] for uidx in upsert_field_idx]

    # sanity check: field name should match
    assert [u.name for u in upsert_fields] == [
        init_data[0][uidx] for uidx in upsert_field_idx
    ]

    # upsert_file_name contains almost-full file import job structure. The only thing
    # missing is configuration.upsert_fields, which is calculated in code from args.
    with open_test_file(
        f"baserow/database/file_import/upsert_{upsert_file_name}_data.json", "rt"
    ) as f:
        update_data = json.load(f)
        update_data["configuration"]["upsert_fields"] = [u.id for u in upsert_fields]
        with patch_filefield_storage():
            job = data_fixture.create_file_import_job(
                data=update_data,
                table=table,
                user=user,
            )
            run_async_job(job.id)
            job.refresh_from_db()
            assert job.finished

    return UpsertData(model=model, text_field=text_field, description=description)


@pytest.mark.parametrize(
    "upsert_field_idx,upsert_file_name",
    [
        ((0,), "text"),
        ((1,), "long_text"),
        ((2,), "number"),
        ((3,), "rating"),
        ((4,), "bool"),
        ((5,), "date"),
        ((6,), "datetime"),
        ((7,), "duration"),
        ((8,), "url"),
        ((9,), "phone"),
        ((10,), "email"),
    ],
)
@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert_for_single_field_type(
    data_fixture,
    patch_filefield_storage,
    open_test_file,
    upsert_field_idx: list[int],
    upsert_file_name: str | None,
):
    """
    test upsert with single field types
    """

    # upsert_file_name contains a 6-element set:
    # one value duplicated on import side: 1 update, 1 insert
    # one value duplicated on both sides + 1 extra in import: 2 updates, 1 insert
    # one value that doesn't have corresponding table value: 1 insert
    prepared = prepare_upsert_data(
        data_fixture,
        patch_filefield_storage,
        open_test_file,
        upsert_field_idx,
        upsert_file_name,
    )

    model, text_field, description = prepared

    # aaa: one updated, one inserted
    # bbb: two updated, one inserted
    # zzz: one inserted
    # updated: 3, inserted: 3
    assert len(model.objects.all()) == 6
    assert len(model.objects.filter(**{text_field.db_column: "aaa"})) == 2
    assert len(model.objects.filter(**{text_field.db_column: "bbb"})) == 3
    assert len(model.objects.filter(**{text_field.db_column: "zzz"})) == 1
    assert len(model.objects.filter(**{description.db_column: "inserted zzz"})) == 1
    assert len(model.objects.filter(**{description.db_column: "inserted aaa"})) == 1
    assert len(model.objects.filter(**{description.db_column: "inserted bbb"})) == 1

    assert len(model.objects.filter(**{description.db_column: "updated aaa"})) == 1
    assert len(model.objects.filter(**{description.db_column: "updated bbb"})) == 2


# test single fields and selected pairs
@pytest.mark.parametrize(
    "upsert_field_idx,upsert_file_name",
    [
        (
            (
                0,
                2,
            ),  # text + number
            "text_number",
        ),
        (
            (
                0,
                4,
            ),  # text + boolean
            "text_boolean",
        ),
        (
            (
                0,
                5,
            ),  # text + date
            "text_date",
        ),
        (
            (
                0,
                6,
            ),
            "text_timestamp",
        ),  # text + timestamp
        (
            (
                0,
                7,
            ),
            "text_duration",
        ),  # text + duration
        (
            (
                2,
                4,
            ),
            "number_boolean",
        ),  # number + boolean
        (
            (
                2,
                5,
            ),
            "number_date",
        ),  # number + date
        (
            (
                2,
                6,
            ),
            "number_timestamp",
        ),  # number + timestamp
        (
            (
                2,
                7,
            ),
            "number_duration",
        ),  # number + duration
        (
            (
                4,
                5,
            ),
            "boolean_date",
        ),  # boolean + date
        (
            (
                4,
                6,
            ),
            "boolean_timestamp",
        ),  # boolean + timestamp
        (
            (
                4,
                7,
            ),
            "boolean_duration",
        ),  # boolean + duration
        (
            (
                5,
                6,
            ),
            "date_timestamp",
        ),  # date +timestamp
        (
            (
                5,
                7,
            ),
            "date_duration",
        ),  # date + duration
        (
            (6, 7),
            "timestamp_duration",
        ),  # timestamp + duration
    ],
)
@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert_for_multiple_field_types(
    data_fixture,
    patch_filefield_storage,
    open_test_file,
    upsert_field_idx: list[int],
    upsert_file_name: str | None,
):
    # upsert_file_name contains 5-element update:
    # one with duplicated on import side, that will produce 1 update + 1 insert
    # one duplicated on table side, that will produce 1 update + 1 insert
    # one new, that will produce 1 insert

    prepared = prepare_upsert_data(
        data_fixture,
        patch_filefield_storage,
        open_test_file,
        upsert_field_idx,
        upsert_file_name,
    )

    model, text_field, description = prepared

    # aaa: one updated, one inserted
    # bbb: one updated, one inserted
    # zzz: one inserted
    # updated: 2, inserted: 3
    assert len(model.objects.all()) == 6
    assert len(model.objects.filter(**{text_field.db_column: "aaa"})) == 2
    assert len(model.objects.filter(**{text_field.db_column: "bbb"})) == 3
    assert len(model.objects.filter(**{text_field.db_column: "zzz"})) == 1
    assert len(model.objects.filter(**{description.db_column: "inserted zzz"})) == 1
    assert len(model.objects.filter(**{description.db_column: "inserted aaa"})) == 1
    assert len(model.objects.filter(**{description.db_column: "inserted bbb"})) == 1

    assert len(model.objects.filter(**{description.db_column: "updated aaa"})) == 1
    assert len(model.objects.filter(**{description.db_column: "updated bbb"})) == 1


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_date_validation(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)

    f1 = data_fixture.create_date_field(table=table, order=1, name="date 1")
    f2 = data_fixture.create_text_field(table=table, order=2, name="text 1")

    model = table.get_model()

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data={
                "data": [
                    ["0000-01-01", "zero"],
                    ["2020-01-01", "one"],
                    ["19999-09-09", "two"],
                ],
            },
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    rows = model.objects.order_by("order").all()
    # first and last are discarded because they're not valid date formats
    assert [
        (
            getattr(r, f1.db_column),
            getattr(r, f2.db_column),
        )
        for r in rows
    ] == [
        (
            date(2020, 1, 1),
            "one",
        )
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_constraints
def test_run_file_import_task_with_field_constraints(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Unique Text Field",
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    model = table.get_model()

    data = {
        "data": [
            ["unique_value_1"],
            ["unique_value_2"],
            ["unique_value_3"],
        ]
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)
    job.refresh_from_db()
    assert job.finished
    assert not job.failed

    rows = model.objects.all()
    assert len(rows) == 3

    data_with_duplicates = {
        "data": [
            ["unique_value_1"],
            ["unique_value_4"],
        ]
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=data_with_duplicates,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    assert not job.failed

    rows = model.objects.all()
    assert len(rows) == 3

    assert "0" in job.report["failing_rows"]
    assert "1" in job.report["failing_rows"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_constraints
def test_run_file_import_task_with_upsert_and_field_constraints(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)

    handler = FieldHandler()
    field_a = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Field A",
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )
    field_b = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="Field B",
        field_constraints=[
            {"type_name": TextTypeUniqueWithEmptyConstraint.constraint_name}
        ],
    )

    model = table.get_model()

    initial_data = {
        "data": [
            ["1", "1"],
            ["2", "2"],
            ["3", "3"],
        ]
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=initial_data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    assert not job.failed
    assert model.objects.count() == 3

    # Data that violates field_b constraint for row "1"
    upsert_data = {
        "data": [
            ["1", "2"],
            ["3", "4"],
        ],
        "configuration": {
            "upsert_fields": [field_a.id],
            "upsert_values": [["1"], ["3"]],
        },
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=upsert_data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    assert not job.failed

    assert "0" in job.report["failing_rows"]
    assert "1" in job.report["failing_rows"]

    values = set(
        (getattr(row, f"field_{field_a.id}"), getattr(row, f"field_{field_b.id}"))
        for row in model.objects.all()
    )
    assert values == {("1", "1"), ("2", "2"), ("3", "3")}


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert_and_valid_skipped_fields(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)

    name_field = data_fixture.create_text_field(table=table, order=1, name="name")
    age_field = data_fixture.create_number_field(table=table, order=2, name="age")
    email_field = data_fixture.create_text_field(table=table, order=3, name="email")

    model = table.get_model()

    initial_data = {
        "data": [
            ["Alice", 25, "alice@example.com"],
            ["Bob", 30, "bob@example.com"],
        ]
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=initial_data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    alice = model.objects.filter(**{name_field.db_column: "Alice"}).first()
    bob = model.objects.filter(**{name_field.db_column: "Bob"}).first()

    assert getattr(alice, email_field.db_column) == "alice@example.com"
    assert getattr(bob, email_field.db_column) == "bob@example.com"

    upsert_data = {
        "data": [
            ["Alice", 26],
            ["Bob", 31],
            ["Charlie", 28],
        ],
        "configuration": {
            "upsert_fields": [name_field.id],
            "upsert_values": [["Alice"], ["Bob"], ["Charlie"]],
            "skipped_fields": [email_field.id],
        },
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=upsert_data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    assert not job.failed
    assert model.objects.count() == 3

    alice = model.objects.filter(**{name_field.db_column: "Alice"}).first()
    bob = model.objects.filter(**{name_field.db_column: "Bob"}).first()
    charlie = model.objects.filter(**{name_field.db_column: "Charlie"}).first()

    assert getattr(alice, age_field.db_column) == 26
    assert getattr(alice, email_field.db_column) == "alice@example.com"

    assert getattr(bob, age_field.db_column) == 31
    assert getattr(bob, email_field.db_column) == "bob@example.com"

    assert getattr(charlie, age_field.db_column) == 28
    assert getattr(charlie, email_field.db_column) is None


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert_and_invalid_skipped_fields(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)

    name_field = data_fixture.create_text_field(table=table, order=1, name="name")

    initial_data = {
        "data": [
            ["Alice", 25],
        ]
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=initial_data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    upsert_data = {
        "data": [
            ["Alice", 26],
        ],
        "configuration": {
            "upsert_fields": [name_field.id],
            "upsert_values": [["Alice"]],
            "skipped_fields": [99999],
        },
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=upsert_data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()

    assert job.failed
    assert job.error == f"The field ID is not found in the table."


@pytest.mark.django_db(transaction=True)
def test_run_file_import_task_with_upsert_and_none_skipped_fields(
    data_fixture, patch_filefield_storage
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)

    name_field = data_fixture.create_text_field(table=table, order=1, name="name")
    age_field = data_fixture.create_number_field(table=table, order=2, name="age")
    email_field = data_fixture.create_text_field(table=table, order=3, name="email")

    model = table.get_model()

    initial_data = {
        "data": [
            ["Alice", 25, "alice@example.com"],
            ["Bob", 30, "bob@example.com"],
        ]
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=initial_data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    alice = model.objects.filter(**{name_field.db_column: "Alice"}).first()
    bob = model.objects.filter(**{name_field.db_column: "Bob"}).first()

    assert getattr(alice, email_field.db_column) == "alice@example.com"
    assert getattr(bob, email_field.db_column) == "bob@example.com"

    upsert_data = {
        "data": [
            ["Alice", 26, "new_alice@example.com"],
            ["Bob", 31, "new_bob@example.com"],
            ["Charlie", 28, "charlie@example.com"],
        ],
        "configuration": {
            "upsert_fields": [name_field.id],
            "upsert_values": [["Alice"], ["Bob"], ["Charlie"]],
            "skipped_fields": None,
        },
    }

    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            data=upsert_data,
            table=table,
            user=user,
            first_row_header=False,
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.finished
    assert not job.failed
    assert model.objects.count() == 3

    alice = model.objects.filter(**{name_field.db_column: "Alice"}).first()
    bob = model.objects.filter(**{name_field.db_column: "Bob"}).first()
    charlie = model.objects.filter(**{name_field.db_column: "Charlie"}).first()

    assert getattr(alice, age_field.db_column) == 26
    assert getattr(alice, email_field.db_column) == "new_alice@example.com"

    assert getattr(bob, age_field.db_column) == 31
    assert getattr(bob, email_field.db_column) == "new_bob@example.com"

    assert getattr(charlie, age_field.db_column) == 28
    assert getattr(charlie, email_field.db_column) == "charlie@example.com"
