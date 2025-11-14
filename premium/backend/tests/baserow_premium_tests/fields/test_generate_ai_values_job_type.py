"""
Tests for GenerateAIValuesJob creation, validation, and job limiting.
"""
from io import BytesIO
from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from baserow_premium.fields.models import GenerateAIValuesJob

from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_rows_mode(premium_data_fixture):
    """Test job creation in ROWS mode with row_ids parameter."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows
    row_ids = [row.id for row in rows]

    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
        row_ids=row_ids,
    )

    assert job.field_id == field.id
    assert job.row_ids == row_ids
    assert job.view_id is None
    assert job.only_empty is False
    assert job.mode == GenerateAIValuesJob.MODES.ROWS


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_view_mode(premium_data_fixture):
    """Test job creation in VIEW mode with view_id parameter."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")
    view = premium_data_fixture.create_grid_view(table=table)

    # Create some rows
    RowHandler().create_rows(user, table, rows_values=[{}, {}])

    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
        view_id=view.id,
    )

    assert job.field_id == field.id
    assert job.row_ids is None
    assert job.view_id == view.id
    assert job.only_empty is False
    assert job.mode == GenerateAIValuesJob.MODES.VIEW


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_table_mode(premium_data_fixture):
    """Test job creation in TABLE mode without row_ids or view_id."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")

    # Create some rows
    RowHandler().create_rows(user, table, rows_values=[{}, {}, {}])

    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
    )

    assert job.field_id == field.id
    assert job.row_ids is None
    assert job.view_id is None
    assert job.only_empty is False
    assert job.mode == GenerateAIValuesJob.MODES.TABLE


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_with_only_empty_flag_rows_mode(premium_data_fixture):
    """Test job creation with only_empty=True in ROWS mode."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}]).created_rows
    row_ids = [row.id for row in rows]

    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
        row_ids=row_ids,
        only_empty=True,
    )

    assert job.only_empty is True
    assert job.mode == GenerateAIValuesJob.MODES.ROWS


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_with_only_empty_flag_view_mode(premium_data_fixture):
    """Test job creation with only_empty=True in VIEW mode."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")
    view = premium_data_fixture.create_grid_view(table=table)

    RowHandler().create_rows(user, table, rows_values=[{}])

    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
        view_id=view.id,
        only_empty=True,
    )

    assert job.only_empty is True
    assert job.mode == GenerateAIValuesJob.MODES.VIEW


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_with_only_empty_flag_table_mode(premium_data_fixture):
    """Test job creation with only_empty=True in TABLE mode."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")

    RowHandler().create_rows(user, table, rows_values=[{}])

    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
        only_empty=True,
    )

    assert job.only_empty is True
    assert job.mode == GenerateAIValuesJob.MODES.TABLE


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_with_nonexistent_field(premium_data_fixture):
    """Test that creating a job with non-existent field_id raises FieldDoesNotExist."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()

    with pytest.raises(FieldDoesNotExist):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=99999,
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_with_nonexistent_view(premium_data_fixture):
    """Test that creating a job with non-existent view_id raises ViewDoesNotExist."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")

    with pytest.raises(ViewDoesNotExist):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field.id,
            view_id=99999,
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_with_nonexistent_rows(premium_data_fixture):
    """Test that creating a job with non-existent row_ids raises RowDoesNotExist."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")

    with pytest.raises(RowDoesNotExist):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field.id,
            row_ids=[99999, 88888],
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_with_partial_invalid_rows(premium_data_fixture):
    """Test that job creation fails if some row_ids don't exist."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}]).created_rows
    valid_row_id = rows[0].id

    with pytest.raises(RowDoesNotExist):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field.id,
            row_ids=[valid_row_id, 99999],
        )


@pytest.mark.django_db
@pytest.mark.field_ai
@pytest.mark.parametrize("params", [lambda view: {}, lambda view: {"view_id": view.id}])
def test_job_limiting_table_or_view_mode(premium_data_fixture, params):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    view = premium_data_fixture.create_grid_view(table=table)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")
    field_2 = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test2'")

    RowHandler().create_rows(user, table, rows_values=[{}])
    # Manually create a job that won't run
    GenerateAIValuesJob.objects.create(user=user, field=field)

    # 2nd job should fail
    with pytest.raises(MaxJobCountExceeded):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field.id,
            **params(view),
            sync=True,
        )

    # It should be possible to schedule a job for a different field on the same table
    JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field_2.id,
        **params(view),
        sync=True,
    )

    # But it should be possible to schedule 2 more jobs for different tables
    table_2 = premium_data_fixture.create_database_table(database=database)
    view_2 = premium_data_fixture.create_grid_view(table=table_2)
    field_2 = premium_data_fixture.create_ai_field(table=table_2, ai_prompt="'test'")

    # This should work on a different table
    JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field_2.id,
        **params(view_2),
        sync=True,
    )
    # Manually create a job that won't run
    GenerateAIValuesJob.objects.create(user=user, field=field_2)
    # Another job on the same table should fail again
    with pytest.raises(MaxJobCountExceeded):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field_2.id,
            **params(view_2),
            sync=True,
        )

    table_3 = premium_data_fixture.create_database_table(database=database)
    view_3 = premium_data_fixture.create_grid_view(table=table_3)
    field_3 = premium_data_fixture.create_ai_field(table=table_3, ai_prompt="'test'")
    JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field_3.id,
        **params(view_3),
        sync=True,
    )
    # Manually create a job that won't run
    GenerateAIValuesJob.objects.create(user=user, field=field_3)
    # Another job on the same table should fail again
    with pytest.raises(MaxJobCountExceeded):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field_3.id,
            **params(view_3),
            sync=True,
        )

    table_4 = premium_data_fixture.create_database_table(database=database)
    view_4 = premium_data_fixture.create_grid_view(table=table_4)
    field_4 = premium_data_fixture.create_ai_field(table=table_4, ai_prompt="'test'")
    # No more than 3 total concurrent jobs should be allowed, so this should fail
    with pytest.raises(MaxJobCountExceeded):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field_4.id,
            **params(view_4),
            sync=True,
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_limiting_not_applied_to_rows_mode(premium_data_fixture):
    """Test that job limiting is NOT applied to ROWS mode."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")

    rows = (
        RowHandler()
        .create_rows(user, table, rows_values=[{} for _ in range(10)])
        .created_rows
    )

    # Should be able to create more than 5 jobs in ROWS mode
    for i in range(7):
        job = JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field.id,
            row_ids=[rows[i].id],
            sync=True,
        )
        assert job is not None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_create_job_view_mode_with_different_table_view(premium_data_fixture):
    """Test that creating a job with a view from a different table fails."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table1 = premium_data_fixture.create_database_table(database=database)
    table2 = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table1, ai_prompt="'test'")
    view_in_table2 = premium_data_fixture.create_grid_view(table=table2)

    with pytest.raises(ViewDoesNotExist):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            field_id=field.id,
            view_id=view_in_table2.id,
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_mode_property_returns_correct_mode(premium_data_fixture):
    """Test that the mode property correctly identifies the job mode."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'test'")
    view = premium_data_fixture.create_grid_view(table=table)

    rows = RowHandler().create_rows(user, table, rows_values=[{}]).created_rows

    # Test ROWS mode
    job_rows = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
        row_ids=[rows[0].id],
        sync=True,
    )
    assert job_rows.mode == GenerateAIValuesJob.MODES.ROWS

    # Test VIEW mode
    job_view = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
        view_id=view.id,
        sync=True,
    )
    assert job_view.mode == GenerateAIValuesJob.MODES.VIEW

    # Test TABLE mode
    job_table = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        field_id=field.id,
        sync=True,
    )
    assert job_table.mode == GenerateAIValuesJob.MODES.TABLE


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_generate_ai_field_value_view_generative_ai(
    patched_rows_updated, premium_data_fixture
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    field = premium_data_fixture.create_ai_field(
        table=table, name="ai", ai_prompt="'Hello'"
    )

    rows = RowHandler().create_rows(user, table, rows_values=[{}]).created_rows

    assert patched_rows_updated.call_count == 0
    JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, row_ids=[rows[0].id]
    )
    assert patched_rows_updated.call_count == 1
    updated_row = patched_rows_updated.call_args[1]["rows"][0]
    assert (
        getattr(updated_row, field.db_column)
        == "Generated with temperature None: Hello"
    )
    assert patched_rows_updated.call_args[1]["updated_field_ids"] == set([field.id])


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_generate_ai_field_value_view_generative_ai_with_temperature(
    patched_rows_updated, premium_data_fixture
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    field = premium_data_fixture.create_ai_field(
        table=table, name="ai", ai_prompt="'Hello'", ai_temperature=0.7
    )

    rows = RowHandler().create_rows(user, table, rows_values=[{}]).created_rows

    JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, row_ids=[rows[0].id]
    )
    updated_row = patched_rows_updated.call_args[1]["rows"][0]
    assert (
        getattr(updated_row, field.db_column) == "Generated with temperature 0.7: Hello"
    )


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_generate_ai_field_value_view_generative_ai_parse_formula(
    patched_rows_updated, premium_data_fixture
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    firstname = premium_data_fixture.create_text_field(table=table, name="firstname")
    lastname = premium_data_fixture.create_text_field(table=table, name="lastname")
    formula = f"concat('Hello ', get('fields.field_{firstname.id}'), ' ', get('fields.field_{lastname.id}'))"
    field = premium_data_fixture.create_ai_field(
        table=table, name="ai", ai_prompt=formula
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{firstname.id}": "Bram", f"field_{lastname.id}": "Wiepjes"},
            ],
        )
        .created_rows
    )

    assert patched_rows_updated.call_count == 0
    JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, row_ids=[rows[0].id]
    )
    assert patched_rows_updated.call_count == 1
    updated_row = patched_rows_updated.call_args[1]["rows"][0]
    assert (
        getattr(updated_row, field.db_column)
        == "Generated with temperature None: Hello Bram Wiepjes"
    )
    assert patched_rows_updated.call_args[1]["updated_field_ids"] == set([field.id])


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_generate_ai_field_value_view_generative_ai_invalid_field(
    patched_rows_updated, premium_data_fixture
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    firstname = premium_data_fixture.create_text_field(table=table, name="firstname")
    formula = "concat('Hello ', get('fields.field_0'))"
    field = premium_data_fixture.create_ai_field(
        table=table, name="ai", ai_prompt=formula
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{f"field_{firstname.id}": "Bram"}],
        )
        .created_rows
    )
    assert patched_rows_updated.call_count == 0
    JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, row_ids=[rows[0].id]
    )
    assert patched_rows_updated.call_count == 1
    updated_row = patched_rows_updated.call_args[1]["rows"][0]
    assert (
        getattr(updated_row, field.db_column)
        == "Generated with temperature None: Hello "
    )


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_ai_values_generation_error.send")
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_generate_ai_field_value_view_generative_ai_invalid_prompt(
    patched_rows_updated, patched_rows_ai_values_generation_error, premium_data_fixture
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    firstname = premium_data_fixture.create_text_field(table=table, name="firstname")
    formula = "concat('Hello ', get('fields.field_0'))"
    field = premium_data_fixture.create_ai_field(
        table=table,
        name="ai",
        ai_generative_ai_type="test_generative_ai_prompt_error",
        ai_prompt=formula,
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{f"field_{firstname.id}": "Bram"}],
        )
        .created_rows
    )

    assert patched_rows_ai_values_generation_error.call_count == 0

    with pytest.raises(GenerativeAIPromptError):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            sync=True,
            field_id=field.id,
            row_ids=[rows[0].id],
        )

    assert patched_rows_updated.call_count == 0
    assert patched_rows_ai_values_generation_error.call_count == 1
    call_args_rows = patched_rows_ai_values_generation_error.call_args[1]["rows"]
    assert len(call_args_rows) == 1
    assert [r.id for r in call_args_rows] == [rows[0].id]
    assert patched_rows_ai_values_generation_error.call_args[1]["field"] == field
    assert (
        patched_rows_ai_values_generation_error.call_args[1]["error_message"]
        == "Test error"
    )


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_generate_ai_field_value_view_generative_ai_with_files(
    patched_rows_updated, premium_data_fixture
):
    storage = get_default_storage()

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )
    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    file_field = premium_data_fixture.create_file_field(
        table=table, order=0, name="File"
    )
    field = premium_data_fixture.create_ai_field(
        table=table,
        name="ai",
        ai_generative_ai_type="test_generative_ai_with_files",
        ai_prompt="'Test prompt'",
        ai_file_field=file_field,
    )
    table_model = table.get_model()
    user_file_1 = UserFileHandler().upload_user_file(
        user, "aifile.txt", BytesIO(b"Text in file"), storage=storage
    )
    values = {f"field_{file_field.id}": [{"name": user_file_1.name}]}
    row = RowHandler().force_create_row(
        user,
        table,
        values,
        table_model,
    )

    assert patched_rows_updated.call_count == 0
    JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, row_ids=[row.id]
    )
    assert patched_rows_updated.call_count == 1
    updated_row = patched_rows_updated.call_args[1]["rows"][0]
    assert "Generated with files" in getattr(updated_row, field.db_column)
    assert "Test prompt" in getattr(updated_row, field.db_column)
    assert patched_rows_updated.call_args[1]["updated_field_ids"] == set([field.id])


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
@patch("baserow.core.jobs.handler.JobHandler.create_and_start_job")
def test_generate_ai_field_value_no_auto_update(
    patched_job_creation, premium_data_fixture
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    text_field = premium_data_fixture.create_text_field(table=table, name="text")
    ai_field = FieldHandler().create_field(
        table=table,
        user=user,
        name="ai",
        type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt=f"get('fields.field_{text_field.id}')",
        ai_temperature=0.7,
        ai_auto_update=False,
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[{text_field.db_column: "test"}],
        send_webhook_events=False,
        send_realtime_update=False,
    ).created_rows

    assert patched_job_creation.call_count == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
@patch("baserow.core.jobs.handler.JobHandler.create_and_start_job")
def test_generate_ai_field_value_auto_update(
    patched_job_creation, premium_data_fixture
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    text_field = premium_data_fixture.create_text_field(table=table, name="text")
    ai_field = FieldHandler().create_field(
        table=table,
        user=user,
        name="ai",
        type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt=f"get('fields.field_{text_field.id}')",
        ai_temperature=0.7,
        ai_auto_update=True,
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{text_field.db_column: "test"}],
            send_webhook_events=False,
            send_realtime_update=False,
        )
        .created_rows
    )

    assert patched_job_creation.call_count == 1

    call_args = patched_job_creation.call_args
    # Verify job was created with correct parameters
    assert call_args.args[0] == user
    assert call_args.args[1] == "generate_ai_values"
    assert call_args.kwargs["field_id"] == ai_field.id
    assert call_args.kwargs["row_ids"] == [r.id for r in rows]


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
@patch("baserow.core.jobs.handler.JobHandler.create_and_start_job")
def test_generate_ai_field_value_auto_update_no_license_user(
    patched_job_creation, premium_data_fixture
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    text_field = premium_data_fixture.create_text_field(table=table, name="text")
    # user has no license, but the license check is done before so this will create
    # a field with auto update enabled for a user without license.
    ai_field = FieldHandler().create_field(
        table=table,
        user=user,
        name="ai",
        type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt=f"get('fields.field_{text_field.id}')",
        ai_temperature=0.7,
        ai_auto_update=True,
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{text_field.db_column: "test"}],
            send_webhook_events=False,
            send_realtime_update=False,
        )
        .created_rows
    )

    # On the first attempt the license check will fail and the auto update will be
    # disabled.
    assert patched_job_creation.call_count == 0
    ai_field.refresh_from_db()
    assert ai_field.ai_auto_update is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_no_user_task_executed(premium_data_fixture):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )

    database = premium_data_fixture.create_database_application(
        user=user, name="database"
    )
    table = premium_data_fixture.create_database_table(name="table", database=database)
    text_field = premium_data_fixture.create_text_field(table=table, name="text")
    ai_field = FieldHandler().create_field(
        table=table,
        user=user,
        name="ai",
        type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt=f"get('fields.field_{text_field.id}')",
        ai_temperature=0.7,
        ai_auto_update=True,
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[{text_field.db_column: "test text value"}],
            send_webhook_events=False,
            send_realtime_update=False,
        )
        .created_rows
    )

    row = rows[0]
    row.refresh_from_db()

    assert (
        getattr(row, ai_field.db_column)
        == "Generated with temperature 0.7: test text value"
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_auto_update_without_user(premium_data_fixture):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    other_user = premium_data_fixture.create_user(
        email="test2@test.nl",
        password="password",
        first_name="Test2",
        has_active_premium_license=True,
    )

    workspace = premium_data_fixture.create_workspace(users=[user, other_user])
    database = premium_data_fixture.create_database_application(
        workspace=workspace, name="database"
    )

    table = premium_data_fixture.create_database_table(name="table", database=database)
    text_field = premium_data_fixture.create_text_field(table=table, name="text")
    ai_field = FieldHandler().create_field(
        table=table,
        user=user,
        name="ai",
        type_name="ai",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt=f"get('fields.field_{text_field.id}')",
        ai_temperature=0.7,
        ai_auto_update=True,
    )

    assert ai_field.ai_auto_update_user_id == user.id
    user.delete()
    ai_field.refresh_from_db()
    assert ai_field.ai_auto_update_user_id is None

    rows = (
        RowHandler()
        .create_rows(
            other_user,
            table,
            rows_values=[{text_field.db_column: "test text value"}],
            send_webhook_events=False,
            send_realtime_update=False,
        )
        .created_rows
    )

    row = rows[0]
    row.refresh_from_db()

    assert getattr(row, ai_field.db_column) is None
    ai_field.refresh_from_db()
    assert ai_field.ai_auto_update is False
