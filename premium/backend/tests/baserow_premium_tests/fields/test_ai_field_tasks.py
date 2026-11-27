from unittest.mock import MagicMock, patch

from django.test.utils import override_settings
from django.utils import timezone

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.test_utils.sentry import make_openai_error, raised_from
from baserow_premium.fields.models import AIFieldScheduledUpdate
from baserow_premium.fields.tasks import (
    generate_scheduled_ai_field_generation,
    schedule_ai_field_generation,
)


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
def test_ai_field_schedule_update_rows_task():
    with patch(
        "baserow_premium.fields.tasks._schedule_generate_ai_value_generation"
    ) as mock_generate_ai_type:
        schedule_ai_field_generation(field_id=1, row_ids=[1, 2, 3, 4])
        schedule_ai_field_generation(field_id=1, row_ids=[3, 4, 5])

        assert mock_generate_ai_type.call_count == 2

    scheduled = list(AIFieldScheduledUpdate.objects.all())
    assert len(scheduled) == 5
    assert [r.row_id for r in scheduled] == [1, 2, 3, 4, 5]


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
def test_ai_field_schedule_update_no_rows_task():
    """
    Test if empty rows list will schedule generation task anyway
    """

    with patch(
        "baserow_premium.fields.tasks._schedule_generate_ai_value_generation"
    ) as mock_generate_ai_type:
        schedule_ai_field_generation(field_id=1, row_ids=[])

        assert mock_generate_ai_type.call_count == 1

    assert AIFieldScheduledUpdate.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_generate_ai_field_from_scheduled_rows(premium_data_fixture):
    """
    Test if the ai value generation task will pick up scheduled rows.
    """

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
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {text_field.db_column: "row 1"},
                {text_field.db_column: "row 2"},
            ],
            send_webhook_events=False,
            send_realtime_update=False,
        )
        .created_rows
    )

    assert AIFieldScheduledUpdate.objects.count() == 0
    row_ids = [r.id for r in rows]

    ai_field = FieldHandler().update_field(
        user=user, field=ai_field, ai_auto_update=True
    )

    assert ai_field.ai_auto_update_user == user

    schedule_ai_field_generation(field_id=ai_field.id, row_ids=row_ids)

    assert AIFieldScheduledUpdate.objects.count() == 0

    for row in rows:
        row.refresh_from_db()
        assert (
            getattr(row, ai_field.db_column)
            == f"Generated with temperature 0.7: row {row.id}"
        )


@pytest.mark.django_db
@patch(
    "baserow_premium.license.handler.LicenseHandler.user_has_feature", return_value=True
)
@override_settings(DEBUG=True)
def test_identity_auto_update_stores_its_user_and_generates_as_the_identity(
    has_feature, premium_data_fixture
):
    from baserow_premium.fields.models import GenerateAIValuesJob
    from baserow_premium.fields.tasks import generate_scheduled_ai_field_generation

    premium_data_fixture.register_fake_generate_ai_type()
    table = premium_data_fixture.create_database_table()
    identity = premium_data_fixture.create_identity(workspace=table.database.workspace)
    ai_field = FieldHandler().create_field(
        identity,
        table,
        "ai",
        name="AI",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_prompt="'Describe this row'",
    )
    row = RowHandler().create_row(identity, table)
    ai_field = FieldHandler().update_field(identity, ai_field, ai_auto_update=True)
    assert ai_field.ai_auto_update_user == identity
    AIFieldScheduledUpdate.objects.create(
        field_id=ai_field.id, row_id=row.id, updated_on=timezone.now()
    )

    generate_scheduled_ai_field_generation(ai_field.id)

    job = GenerateAIValuesJob.objects.get()
    assert job.finished
    assert job.user == identity
    row.refresh_from_db()
    assert (
        getattr(row, ai_field.db_column)
        == "Generated with temperature None: Describe this row"
    )
    assert row.last_modified_by_id == identity.id
    assert has_feature.call_args.args[1] == identity


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_failed_scheduled_generation_keeps_rows_for_the_next_periodic_run(
    premium_data_fixture,
):
    premium_data_fixture.register_fake_generate_ai_type()
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        ai_prompt="'Test'",
        ai_auto_update=True,
        ai_auto_update_user=user,
    )
    rows = RowHandler().create_rows(user, table, rows_values=[{}]).created_rows
    AIFieldScheduledUpdate.objects.create(
        field_id=ai_field.id,
        row_id=rows[0].id,
        updated_on=timezone.now(),
    )
    # Rows scheduled while the job ran would normally start another run at once.
    flag = MagicMock()
    flag.is_set.return_value = True
    prompt_error = raised_from(
        GenerativeAIPromptError("You have no credits remaining."),
        make_openai_error(429),
    )

    with (
        patch(
            "baserow.test_utils.fixtures.generative_ai."
            "TestGenerativeAIModelType.prompt",
            side_effect=prompt_error,
        ),
        patch(
            "baserow_premium.fields.tasks._get_singleton_autoreschedule_flag",
            return_value=flag,
        ),
        patch(
            "baserow_premium.fields.tasks._schedule_generate_ai_value_generation"
        ) as mock_schedule,
    ):
        # The failure was sent to the user, so the task doesn't raise it.
        generate_scheduled_ai_field_generation(ai_field.id)

    assert AIFieldScheduledUpdate.objects.filter(field_id=ai_field.id).count() == 1
    mock_schedule.assert_not_called()
