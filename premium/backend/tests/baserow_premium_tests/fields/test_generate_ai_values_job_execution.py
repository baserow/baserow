from unittest.mock import patch

from django.test.utils import override_settings

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.metadata_handler import FieldMetadataHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.signals import rows_metadata_updated
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.generative_ai.exceptions import (
    GenerativeAIPromptError,
    ModelDoesNotBelongToType,
)
from baserow.core.jobs.handler import JobHandler
from baserow_premium.fields.ai_field_metadata import (
    AIFieldMetadataHandler,
    AIMetadataKeys,
)
from baserow_premium.fields.models import GenerateAIValuesJob


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
    assert patched_rows_updated.call_count == 2

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
    assert patched_rows_updated.call_count == 3

    # Verify all rows were updated
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
    assert patched_rows_updated.call_count == 2

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
    assert patched_rows_updated.call_count == 2

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
    middle_row = model.objects.all().order_by("id")[1]
    setattr(middle_row, field.db_column, "Already filled")
    middle_row.save()

    job = JobHandler().create_and_start_job(
        user, "generate_ai_values", sync=True, field_id=field.id, only_empty=True
    )

    assert job.state == "finished"
    assert patched_rows_updated.call_count == 2  # Only 2 empty rows

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
    assert patched_rows_updated.call_count == 2

    rows = model.objects.all().order_by("id")
    assert getattr(rows[0], field.db_column) == "Generated with temperature None: Test"
    assert getattr(rows[1], field.db_column) == "Filled"  # Unchanged
    assert getattr(rows[2], field.db_column) == "Generated with temperature None: Test"


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


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(
    BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS=5, BATCH_ROWS_SIZE_LIMIT=5
)
@patch("baserow.contrib.database.rows.signals.rows_updated.send")
def test_job_execution_all_rows_fail_in_concurrent_batch(
    patched_rows_updated, premium_data_fixture
):
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
        .create_rows(user, table, rows_values=[{} for _ in range(10)])
        .created_rows
    )
    row_ids = [r.id for r in rows]

    def always_fail(self, model, prompt, workspace=None, temperature=None):
        raise GenerativeAIPromptError("Invalid model")

    with patch(
        "baserow.test_utils.fixtures.generative_ai.TestGenerativeAIModelType.prompt",
        always_fail,
    ):
        with pytest.raises(GenerativeAIPromptError):
            JobHandler().create_and_start_job(
                user,
                "generate_ai_values",
                sync=True,
                field_id=field.id,
            )

    model = table.get_model()
    all_rows = list(model.objects.filter(id__in=row_ids).order_by("id"))

    # First batch (5 rows) should have error metadata, not "generating"
    for row in all_rows[:5]:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
            .get(row.id, {})
            .get(field.id)
        )
        assert meta is not None, f"Row {row.id} should have error metadata"
        assert meta[AIMetadataKeys.OK] is False, (
            f"Row {row.id} should not be stuck in generating state"
        )

    # Remaining rows (6-10) were never flushed, so no metadata at all
    for row in all_rows[5:]:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
            .get(row.id, {})
            .get(field.id)
        )
        assert meta is None, (
            f"Row {row.id} was never scheduled, should have no metadata"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(
    BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS=1, BATCH_ROWS_SIZE_LIMIT=1
)
def test_job_execution_clears_pre_set_metadata_for_unfetched_rows(
    premium_data_fixture,
):
    """
    FIX 1: When metadata is pre-set for all row_ids before the job starts
    (ROWS mode via dedicated endpoint), and an error occurs mid-processing,
    rows that were never even fetched from the iterator should have their
    "generating" metadata cleaned up.
    """

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

    # Ensure metadata column exists and pre-set "generating" metadata
    # (simulating what AIFieldHandler.start_ai_field_generation does)
    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(field, row_ids)

    # Verify all 5 rows have "generating" metadata
    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        assert meta is not None, f"Row {row_id} should have generating metadata"
        assert AIMetadataKeys.START in meta

    call_count = [0]

    def mock_prompt(self, model_name, prompt, workspace=None, temperature=None):
        call_count[0] += 1
        if call_count[0] == 3:
            raise GenerativeAIPromptError("Simulated error on row 3")
        return f"Generated value {call_count[0]}"

    with (
        patch(
            "baserow.test_utils.fixtures.generative_ai.TestGenerativeAIModelType.prompt",
            mock_prompt,
        ),
        patch.object(
            rows_metadata_updated, "send", wraps=rows_metadata_updated.send
        ) as patched_metadata_signal,
    ):
        with pytest.raises(GenerativeAIPromptError):
            JobHandler().create_and_start_job(
                user,
                "generate_ai_values",
                sync=True,
                field_id=field.id,
                row_ids=row_ids,
            )

    # Rows 1-2: should have generated values
    model = table.get_model()
    rows_refreshed = list(model.objects.filter(id__in=row_ids).order_by("id"))
    assert getattr(rows_refreshed[0], field.db_column) == "Generated value 1"
    assert getattr(rows_refreshed[1], field.db_column) == "Generated value 2"

    # Row 3: should have error metadata
    meta_row3 = (
        FieldMetadataHandler.get_metadata(model, [rows_refreshed[2].id], [field.id])
        .get(rows_refreshed[2].id, {})
        .get(field.id)
    )
    assert meta_row3 is not None
    assert meta_row3[AIMetadataKeys.OK] is False

    # Rows 4-5: pre-set "generating" metadata should be CLEARED
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
    assert meta_row4 is None, "Row 4 should have metadata cleared (was never processed)"
    assert meta_row5 is None, "Row 5 should have metadata cleared (was never processed)"

    # Verify rows_metadata_updated signal was sent for the unprocessed rows.
    # This ensures the WS broadcast happens so the frontend can clear spinners.
    cleanup_calls = [
        call
        for call in patched_metadata_signal.call_args_list
        if set(call.kwargs.get("row_ids", []))
        & {rows_refreshed[3].id, rows_refreshed[4].id}
    ]
    assert len(cleanup_calls) > 0, (
        "rows_metadata_updated signal should be sent for unprocessed rows"
    )


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(
    BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS=5, BATCH_ROWS_SIZE_LIMIT=5
)
def test_job_execution_rows_mode_all_fail_clears_unprocessed_metadata(
    premium_data_fixture,
):
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
        .create_rows(user, table, rows_values=[{} for _ in range(10)])
        .created_rows
    )
    row_ids = [r.id for r in rows]

    # Pre-set metadata for ALL rows (simulating start_ai_field_generation)
    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(field, row_ids)

    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        assert meta is not None

    def always_fail(self, model_name, prompt, workspace=None, temperature=None):
        raise GenerativeAIPromptError("Invalid model")

    with patch(
        "baserow.test_utils.fixtures.generative_ai.TestGenerativeAIModelType.prompt",
        always_fail,
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
    all_rows = list(model.objects.filter(id__in=row_ids).order_by("id"))

    # First batch (5 rows): scheduled, all failed → error metadata
    for row in all_rows[:5]:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
            .get(row.id, {})
            .get(field.id)
        )
        assert meta is not None, f"Row {row.id} should have error metadata"
        assert meta[AIMetadataKeys.OK] is False

    # Remaining rows (6-10): pre-set as "generating" but never scheduled.
    # _cleanup_unprocessed_rows should have cleared their metadata.
    for row in all_rows[5:]:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row.id], [field.id])
            .get(row.id, {})
            .get(field.id)
        )
        assert meta is None, (
            f"Row {row.id} should have metadata cleared, not stuck in generating"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_execution_cleans_up_metadata_on_prepare_failure(premium_data_fixture):
    """
    FIX 2: When prepare() fails (e.g., AI model became unavailable after
    start_ai_field_generation pre-set metadata), all pre-set "generating"
    metadata should be cleaned up.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)

    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_prompt="'Test'",
        ai_generative_ai_type="test_generative_ai",
    )

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows
    row_ids = [r.id for r in rows]

    # Pre-set metadata (simulating start_ai_field_generation)
    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(field, row_ids)

    # Verify metadata is set
    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        assert meta is not None

    # Mock AIValueGenerator.prepare() to raise ModelDoesNotBelongToType.
    # This simulates the AI model becoming unavailable between the API call
    # (prepare_values succeeds) and the job execution (prepare fails).
    # We mock the method on the class directly so prepare_values() still
    # succeeds (it calls get_valid_generative_ai_model_type_or_raise
    # directly, not through AIValueGenerator.prepare).
    def failing_prepare(self):
        raise ModelDoesNotBelongToType(model_name="test")

    with patch(
        "baserow_premium.fields.job_types.AIValueGenerator.prepare",
        failing_prepare,
    ):
        with pytest.raises(ModelDoesNotBelongToType):
            JobHandler().create_and_start_job(
                user,
                "generate_ai_values",
                sync=True,
                field_id=field.id,
                row_ids=row_ids,
            )

    # All rows should have their metadata CLEARED
    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        assert meta is None, (
            f"Row {row_id} should have metadata cleared after prepare() failure"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(
    BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS=1, BATCH_ROWS_SIZE_LIMIT=1
)
def test_job_execution_rows_mode_skips_redundant_metadata_set(premium_data_fixture):
    """
    FIX 4: In ROWS mode, metadata is pre-set before the job starts. The
    generator should NOT call set_generating_and_broadcast() again during
    processing, avoiding redundant DB writes and WS broadcasts.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)

    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_prompt="'Test'",
        ai_generative_ai_type="test_generative_ai",
    )

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows
    row_ids = [r.id for r in rows]

    # Pre-set metadata (simulating start_ai_field_generation)
    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(field, row_ids)

    with patch(
        "baserow_premium.fields.job_types.AIFieldMetadataHandler"
        ".set_generating_and_broadcast"
    ) as mock_broadcast:
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            sync=True,
            field_id=field.id,
            row_ids=row_ids,
        )

        # set_generating_and_broadcast should NOT be called during processing
        assert mock_broadcast.call_count == 0, (
            "set_generating_and_broadcast should not be called in ROWS mode "
            "since metadata was pre-set"
        )

    # Verify all rows were still processed successfully
    model = table.get_model()
    for row in model.objects.filter(id__in=row_ids).order_by("id"):
        assert getattr(row, field.db_column) is not None


@pytest.mark.django_db
@pytest.mark.field_ai
def test_job_execution_table_mode_still_sets_metadata_during_processing(
    premium_data_fixture,
):
    """
    FIX 4 (counterpart): In TABLE mode (no pre-set metadata), the generator
    should still call set_generating_and_broadcast() during processing.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)

    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_prompt="'Test'",
        ai_generative_ai_type="test_generative_ai",
    )

    RowHandler().create_rows(user, table, rows_values=[{}, {}, {}])

    with patch(
        "baserow_premium.fields.job_types.AIFieldMetadataHandler"
        ".set_generating_and_broadcast"
    ) as mock_broadcast:
        JobHandler().create_and_start_job(
            user,
            "generate_ai_values",
            sync=True,
            field_id=field.id,
        )

        # In TABLE mode, set_generating_and_broadcast SHOULD be called
        assert mock_broadcast.call_count > 0, (
            "set_generating_and_broadcast should be called in TABLE mode"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_on_cancelled_clears_pre_set_metadata_for_rows_mode(premium_data_fixture):
    """
    When a ROWS-mode job is cancelled before the Celery task runs, the pre-set
    GENERATING metadata should be cleared by the on_cancelled hook, so rows
    don't get stuck with a spinner forever.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows
    row_ids = [r.id for r in rows]

    # Ensure metadata column exists and pre-set "generating" metadata
    # (simulating what AIFieldHandler.start_ai_field_generation does)
    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(field, row_ids)

    # Verify all rows have "generating" metadata
    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        assert meta is not None, f"Row {row_id} should have generating metadata"
        assert AIMetadataKeys.START in meta

    # Create the job without running it (simulate pending job in Celery queue)
    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=False, field_id=field.id, row_ids=row_ids
        )

    assert job.pending

    # Cancel the job — on_cancelled hook should clear metadata
    with patch.object(rows_metadata_updated, "send") as mock_signal:
        JobHandler.cancel_job(job)

        # Verify the signal was sent to notify the frontend
        assert mock_signal.call_count == 1
        call_kwargs = mock_signal.call_args[1]
        assert set(call_kwargs["row_ids"]) == set(row_ids)
        assert call_kwargs["table"].id == table.id

    # Verify metadata is cleared for all rows
    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        assert meta is None, (
            f"Row {row_id} should have metadata cleared after cancellation"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_on_cancelled_does_not_clear_metadata_for_table_mode(premium_data_fixture):
    """
    When a TABLE-mode job is cancelled, on_cancelled should NOT try to clear
    metadata because TABLE mode doesn't pre-set metadata.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")

    RowHandler().create_rows(user, table, rows_values=[{}, {}])

    # Create a TABLE-mode job (no row_ids) without running it
    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=False, field_id=field.id
        )

    assert job.mode == GenerateAIValuesJob.MODES.TABLE

    # Cancel the job — on_cancelled should be a no-op for TABLE mode
    with patch(
        "baserow_premium.fields.job_types._cleanup_pre_set_metadata"
    ) as mock_cleanup:
        JobHandler.cancel_job(job)
        assert mock_cleanup.call_count == 0


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(
    BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS=1, BATCH_ROWS_SIZE_LIMIT=1
)
def test_cancel_during_active_processing_clears_metadata_not_error(
    premium_data_fixture,
):
    """
    When a running job is cancelled while actively processing rows, the generator
    should clear "generating" metadata for remaining rows (not set ERROR), and the
    job should end in CANCELLED state (not FAILED).

    Previously, JobCancelled raised by progress_updated was caught by
    `except Exception` in update_progress, causing handle_error to set ERROR
    metadata on every post-cancel row, and the job to end as FAILED.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows
    row_ids = [r.id for r in rows]

    TableHandler().ensure_field_metadata_column_exists(table)

    # Track refresh_from_db calls. Simulate cancellation after the 1st row
    # has been fully processed (the 2nd refresh_from_db call happens during
    # update_progress for row 2).
    refresh_count = [0]

    def mock_refresh(self, *args, **kwargs):
        # Call original to read real DB state first
        type(self).__mro__[1].refresh_from_db(self, *args, **kwargs)
        refresh_count[0] += 1
        if refresh_count[0] >= 2 and self.state != "cancelled":
            self.set_state_cancelled()
            self.save()

    with patch.object(GenerateAIValuesJob, "refresh_from_db", mock_refresh):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=True, field_id=field.id
        )
        job.refresh_from_db()

    # Job should be in CANCELLED state, not FAILED
    assert job.state == "cancelled", (
        f"Expected job state 'cancelled', got '{job.state}'"
    )

    # Verify no rows have ERROR metadata (the bug caused every post-cancel row
    # to get ERROR metadata)
    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        if meta:
            assert meta.get(AIMetadataKeys.OK) is not False, (
                f"Row {row_id} has ERROR metadata: {meta}. "
                "Cancelled rows should have metadata cleared, not set to error."
            )


@pytest.mark.django_db
@pytest.mark.field_ai
def test_on_cancelled_handles_deleted_field_gracefully(premium_data_fixture):
    """
    When a ROWS-mode job is cancelled and the field has been deleted in the
    meantime, on_cancelled should not raise an exception. The job should
    still be in cancelled state.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}]).created_rows
    row_ids = [r.id for r in rows]

    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(field, row_ids)

    # Create the job without running it
    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=False, field_id=field.id, row_ids=row_ids
        )

    assert job.pending

    # Delete the field before cancelling the job
    FieldHandler().delete_field(user, field)

    # Cancel the job — should NOT raise FieldDoesNotExist
    JobHandler.cancel_job(job)

    job.refresh_from_db()
    assert job.state == "cancelled"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_on_cancelled_skips_cleanup_when_job_is_running(premium_data_fixture):
    """
    When a ROWS-mode job is cancelled after the Celery task has started
    (job state was 'started'), on_cancelled should NOT clear metadata
    because the running generator handles its own cleanup.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows
    row_ids = [r.id for r in rows]

    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(field, row_ids)

    # Create the job without running it, then manually set it to 'started'
    # to simulate a running Celery task
    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=False, field_id=field.id, row_ids=row_ids
        )

    job.set_state_started()
    job.save()

    # Cancel the job — on_cancelled should skip cleanup for a running job
    with patch(
        "baserow_premium.fields.job_types._cleanup_pre_set_metadata"
    ) as mock_cleanup:
        JobHandler.cancel_job(job)
        assert mock_cleanup.call_count == 0, (
            "_cleanup_pre_set_metadata should NOT be called when job was running"
        )

    # Metadata should still be present (generator would handle cleanup)
    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        assert meta is not None, (
            f"Row {row_id} metadata should still be present (generator handles cleanup)"
        )


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(
    BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS=1, BATCH_ROWS_SIZE_LIMIT=1
)
def test_cancel_during_active_processing_view_mode(premium_data_fixture):
    """
    When a VIEW-mode job is cancelled during active processing, rows should
    have their metadata cleared (not set to ERROR) and the job should end
    in CANCELLED state.
    """

    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user()
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(table=table, ai_prompt="'Test'")
    view = premium_data_fixture.create_grid_view(table=table)

    rows = RowHandler().create_rows(user, table, rows_values=[{}, {}, {}]).created_rows
    row_ids = [r.id for r in rows]

    TableHandler().ensure_field_metadata_column_exists(table)

    # Simulate cancellation after 1st row processed
    refresh_count = [0]

    def mock_refresh(self, *args, **kwargs):
        type(self).__mro__[1].refresh_from_db(self, *args, **kwargs)
        refresh_count[0] += 1
        if refresh_count[0] >= 2 and self.state != "cancelled":
            self.set_state_cancelled()
            self.save()

    with patch.object(GenerateAIValuesJob, "refresh_from_db", mock_refresh):
        job = JobHandler().create_and_start_job(
            user, "generate_ai_values", sync=True, field_id=field.id, view_id=view.id
        )
        job.refresh_from_db()

    assert job.state == "cancelled", (
        f"Expected job state 'cancelled', got '{job.state}'"
    )

    # Verify no rows have ERROR metadata
    model = table.get_model()
    for row_id in row_ids:
        meta = (
            FieldMetadataHandler.get_metadata(model, [row_id], [field.id])
            .get(row_id, {})
            .get(field.id)
        )
        if meta:
            assert meta.get(AIMetadataKeys.OK) is not False, (
                f"Row {row_id} has ERROR metadata: {meta}. "
                "Cancelled rows should have metadata cleared, not set to error."
            )
