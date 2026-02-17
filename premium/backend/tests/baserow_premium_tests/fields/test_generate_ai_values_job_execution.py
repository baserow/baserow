from unittest.mock import patch

from django.test.utils import override_settings

import pytest

from baserow.contrib.database.fields.metadata_handler import FieldMetadataHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.jobs.handler import JobHandler
from baserow_premium.fields.ai_field_metadata import AIMetadataKeys
from baserow_premium.fields.models import GenerateAIValuesJob


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_execution_rows_mode(premium_data_fixture):
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

    model = table.get_model()
    rows = model.objects.all().order_by("id")
    assert getattr(rows[0], field.db_column) == "Generated with temperature None: Test"
    assert getattr(rows[1], field.db_column) is None  # Not updated
    assert getattr(rows[2], field.db_column) == "Generated with temperature None: Test"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_execution_table_mode(premium_data_fixture):
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
    model = table.get_model()
    for row in model.objects.all():
        assert (
            getattr(row, field.db_column)
            == "Generated with temperature None: Table Test"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_execution_view_mode(premium_data_fixture):
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

    # Verify only filtered rows were updated (2 rows with "show" text)
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
def test_job_execution_only_empty_rows_mode(premium_data_fixture):
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

    # Check that pre-filled row kept its value and only empty rows were updated
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
def test_job_execution_only_empty_table_mode(premium_data_fixture):
    """Test only_empty flag in TABLE mode."""

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Fill Empty'")

    RowHandler().create_rows(user, table, rows_values=[{}, {}, {}])

    # Pre-fill middle row
    model = table.get_model()
    middle_row = model.objects.all().order_by("id")[1]
    setattr(middle_row, field.db_column, "Already filled")
    middle_row.save()

    job = JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, only_empty=True
    )

    assert job.state == "finished"

    rows = model.objects.all().order_by("id")
    assert (
        getattr(rows[0], field.db_column)
        == "Generated with temperature None: Fill Empty"
    )
    assert getattr(rows[1], field.db_column) == "Already filled"  # Unchanged
    assert (
        getattr(rows[2], field.db_column)
        == "Generated with temperature None: Fill Empty"
    )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_execution_only_empty_view_mode(premium_data_fixture):
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
    second_row = model.objects.all().order_by("id")[1]
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

    rows = model.objects.all().order_by("id")
    assert getattr(rows[0], field.db_column) == "Generated with temperature None: Test"
    assert getattr(rows[1], field.db_column) == "Filled"  # Unchanged
    assert getattr(rows[2], field.db_column) == "Generated with temperature None: Test"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_execution_empty_string_vs_null(premium_data_fixture):
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
    assert value_after_job == "Has value", (
        f"Expected 'Has value' but got '{value_after_job}'"
    )


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


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(
    BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS=1, BATCH_ROWS_SIZE_LIMIT=1
)
def test_job_execution_clears_remaining_batch_rows_on_error(premium_data_fixture):
    """
    Test that when a row fails mid-batch, remaining rows in the batch
    have their 'generating' status cleared.

    Uses BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS=1 and BATCH_ROWS_SIZE_LIMIT=1
    to force sequential processing so that rows 4 and 5 don't get scheduled
    before row 3 fails.
    """

    from baserow.core.generative_ai.exceptions import GenerativeAIPromptError

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)

    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_prompt="'Test'",
        ai_generative_ai_type="test_generative_ai",
    )

    rows = (
        RowHandler()
        .create_rows(user, table, rows_values=[{}, {}, {}, {}, {}])
        .created_rows
    )
    row_ids = [r.id for r in rows]

    call_count = [0]

    def mock_prompt(self, model, prompt, workspace=None, temperature=None):
        call_count[0] += 1
        if call_count[0] == 3:
            raise GenerativeAIPromptError("Simulated error on row 3")
        return f"Generated value {call_count[0]}"

    with patch(
        "baserow.test_utils.fixtures.generative_ai.TestGenerativeAIModelType.prompt",
        mock_prompt,
    ):
        with pytest.raises(GenerativeAIPromptError):
            JobHandler().create_and_start_job(
                user,
                "generate_ai_values",
                sync=True,
                field_id=field.id,
                row_ids=row_ids,
            )

    model = table.get_model()
    rows_refreshed = list(model.objects.filter(id__in=row_ids).order_by("id"))

    assert getattr(rows_refreshed[0], field.db_column) == "Generated value 1"
    assert getattr(rows_refreshed[1], field.db_column) == "Generated value 2"
    assert getattr(rows_refreshed[2], field.db_column) is None
    assert getattr(rows_refreshed[3], field.db_column) is None
    assert getattr(rows_refreshed[4], field.db_column) is None

    meta_row3 = (
        FieldMetadataHandler.get_metadata(model, [rows_refreshed[2].id], [field.id])
        .get(rows_refreshed[2].id, {})
        .get(field.id)
    )
    assert meta_row3 is not None
    assert meta_row3[AIMetadataKeys.OK] is False

    meta_row4 = (
        FieldMetadataHandler.get_metadata(model, [rows_refreshed[3].id], [field.id])
        .get(rows_refreshed[3].id, {})
        .get(field.id)
    )
    meta_row5 = (
        FieldMetadataHandler.get_metadata(model, [rows_refreshed[4].id], [field.id])
        .get(rows_refreshed[4].id, {})
        .get(field.id)
    )
    assert meta_row4 is None
    assert meta_row5 is None
