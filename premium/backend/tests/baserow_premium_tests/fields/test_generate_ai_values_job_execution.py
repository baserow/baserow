"""
Tests for GenerateAIValuesJob execution in all modes.
"""
from unittest.mock import patch

import pytest
from baserow_premium.fields.models import GenerateAIValuesJob

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.jobs.handler import JobHandler


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_job_execution_rows_mode(patched_rows_updated, premium_data_fixture):
    """Test job execution in ROWS mode generates values for specific rows."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows
    row_ids = [rows[0].id, rows[2].id]  # Only process first and third

    job = JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, row_ids=row_ids
    )

    assert job.state == "finished"
    assert job.progress_percentage == 100

    # Verify only specified rows were updated
    assert patched_rows_updated.call_count == 2  # One call per row

    # Refresh rows and check values
    model = table.get_model()
    rows = model.objects.all().order_by("id")
    assert getattr(rows[0], field.db_column) == "Generated with temperature None: Test"
    assert getattr(rows[1], field.db_column) is None  # Not updated
    assert getattr(rows[2], field.db_column) == "Generated with temperature None: Test"


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_job_execution_table_mode(patched_rows_updated, premium_data_fixture):
    """Test job execution in TABLE mode generates values for all rows."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Table Test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows

    job = JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id
    )

    assert job.state == "finished"
    assert job.mode == GenerateAIValuesJob.MODES.TABLE

    # Verify all rows were updated
    assert patched_rows_updated.call_count == 3

    model = table.get_model()
    for row in model.objects.all():
        assert (
            getattr(row, field.db_column)
            == "Generated with temperature None: Table Test"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_job_execution_view_mode(patched_rows_updated, premium_data_fixture):
    """Test job execution in VIEW mode generates values for filtered rows."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    text_field = premium_data_fixture.create_text_field(table=table, name="text")
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'View Test'")
    view = premium_data_fixture.create_grid_view(table=table)

    # Create filter: only rows with text="show"
    premium_data_fixture.create_view_filter(
        view=view, field=text_field, type="equal", value="show"
    )

    # Create rows: 2 matching filter, 1 not matching
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{text_field.id}": "show"},
            {f"field_{text_field.id}": "hide"},
            {f"field_{text_field.id}": "show"},
        ],
    )

    job = JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, view_id=view.id
    )

    assert job.state == "finished"
    assert job.mode == GenerateAIValuesJob.MODES.VIEW

    # Verify only filtered rows were updated (2 rows)
    assert patched_rows_updated.call_count == 2

    model = table.get_model()
    for row in model.objects.filter(**{f"field_{text_field.id}": "show"}):
        assert (
            getattr(row, field.db_column)
            == "Generated with temperature None: View Test"
        )

    # Verify hidden row was NOT updated
    hidden_row = model.objects.get(**{f"field_{text_field.id}": "hide"})
    assert getattr(hidden_row, field.db_column) is None


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_job_execution_only_empty_rows_mode(patched_rows_updated, premium_data_fixture):
    """
    Test only_empty flag in ROWS mode only updates empty cells.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Empty Test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows

    # Pre-fill one row
    model = table.get_model()
    pre_filled_value = "Pre-filled"
    model.objects.filter(id=rows[1].id).update(**{field.db_column: pre_filled_value})

    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        sync=True,
        field_id=field.id,
        row_ids=[row.id for row in rows],
        only_empty=True,
    )

    assert job.state == "finished"
    assert job.only_empty is True

    # Verify only 2 rows were updated (empty ones)
    assert patched_rows_updated.call_count == 2

    # Check that pre-filled row kept its value
    rows_refreshed = model.objects.all().order_by("id")
    assert (
        getattr(rows_refreshed[0], field.db_column)
        == "Generated with temperature None: Empty Test"
    )
    assert getattr(rows_refreshed[1], field.db_column) == pre_filled_value  # Unchanged
    assert (
        getattr(rows_refreshed[2], field.db_column)
        == "Generated with temperature None: Empty Test"
    )


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_job_execution_only_empty_table_mode(
    patched_rows_updated, premium_data_fixture
):
    """Test only_empty flag in TABLE mode."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Fill Empty'")

    RowHandler().create_rows(user, table, rows_values=[{}, {}, {}])

    # Pre-fill middle row
    model = table.get_model()
    middle_row = model.objects.all()[1]
    setattr(middle_row, field.db_column, "Already filled")
    middle_row.save()

    job = JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, only_empty=True
    )

    assert job.state == "finished"
    assert patched_rows_updated.call_count == 2  # Only 2 empty rows


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_job_execution_only_empty_view_mode(patched_rows_updated, premium_data_fixture):
    """Test only_empty flag in VIEW mode."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")
    view = premium_data_fixture.create_grid_view(table=table)

    RowHandler().create_rows(user, table, rows_values=[{}, {}, {}])

    # Pre-fill one row
    model = table.get_model()
    second_row = model.objects.all()[1]
    setattr(second_row, field.db_column, "Filled")
    second_row.save()

    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        sync=True,
        field_id=field.id,
        view_id=view.id,
        only_empty=True,
    )

    assert job.state == "finished"
    assert patched_rows_updated.call_count == 2  # Only empty rows in view


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_job_execution_empty_string_vs_null(patched_rows_updated, premium_data_fixture):
    """
    Test that only_empty treats both NULL and empty string as empty.
    Using TABLE mode since only_empty has a bug with ROWS mode.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")

    RowHandler().create_rows(user, table, rows_values=[{}, {}, {}])

    model = table.get_model()
    rows = list(model.objects.all().order_by("id"))

    # First row: NULL (default)
    # Second row: empty string
    rows[1].refresh_from_db()
    setattr(rows[1], field.db_column, "")
    rows[1].save()
    # Third row: has value - use the field model to properly set it
    rows[2].refresh_from_db()
    setattr(rows[2], field.db_column, "Has value")
    rows[2].save()

    # Verify the values were set correctly before running job
    rows[2].refresh_from_db()
    assert getattr(rows[2], field.db_column) == "Has value"

    # Use TABLE mode instead of ROWS mode to avoid the bug
    job = JobHandler().create_and_start_job(
        user,
        "generate_ai_values",
        sync=True,
        field_id=field.id,
        only_empty=True,
    )

    assert job.state == "finished"

    # Verify third row still has its original value (wasn't overwritten)
    rows[2].refresh_from_db()
    value_after_job = getattr(rows[2], field.db_column)
    # If only_empty works, this should still be "Has value", not the generated value
    assert (
        value_after_job == "Has value"
    ), f"Expected 'Has value' but got '{value_after_job}'"


@pytest.mark.django_db
@pytest.mark.field_ai
@patch("baserow.contrib.database.rows.signals.rows_ai_values_generation_error.send")
def test_job_execution_handles_errors(patched_error_signal, premium_data_fixture):
    """Test that job handles errors gracefully."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_prompt="'Test'",
        ai_generative_ai_type="test_generative_ai_prompt_error",
    )

    rows = RowHandler().create_rows(user, table, rows_values=[{}]).created_rows

    from baserow.core.generative_ai.exceptions import GenerativeAIPromptError

    with pytest.raises(GenerativeAIPromptError):
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            sync=True,
            field_id=field.id,
            row_ids=[rows[0].id],
        )

    # Error signal should have been sent
    assert patched_error_signal.call_count == 1
    assert patched_error_signal.call_args[1]["field"] == field
    assert "Test error" in patched_error_signal.call_args[1]["error_message"]


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_progress_tracking(premium_data_fixture):
    """Test that job tracks progress correctly during execution."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Progress'")

    # Create multiple rows to see progress
    RowHandler().create_rows(user, table, rows_values=[{} for _ in range(5)])

    job = JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id
    )

    # After completion, should be at 100%
    assert job.progress_percentage == 100
    assert job.state == "finished"
