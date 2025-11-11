from io import BytesIO
from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from baserow_premium.fields.tasks import generate_ai_values_for_rows

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler


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
    generate_ai_values_for_rows(user.id, field.id, [rows[0].id])
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

    generate_ai_values_for_rows(user.id, field.id, [rows[0].id])
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
    generate_ai_values_for_rows(user.id, field.id, [rows[0].id])
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
    generate_ai_values_for_rows(user.id, field.id, [rows[0].id])
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
        generate_ai_values_for_rows(user.id, field.id, [rows[0].id])

    assert patched_rows_updated.call_count == 0
    assert patched_rows_ai_values_generation_error.call_count == 1
    call_args_rows = patched_rows_ai_values_generation_error.call_args[1]["rows"]
    assert len(call_args_rows) == 1
    assert rows[0].id == call_args_rows[0].id
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
    generate_ai_values_for_rows(user.id, field.id, [row.id])
    assert patched_rows_updated.call_count == 1
    updated_row = patched_rows_updated.call_args[1]["rows"][0]
    assert "Generated with files" in getattr(updated_row, field.db_column)
    assert "Test prompt" in getattr(updated_row, field.db_column)
    assert patched_rows_updated.call_args[1]["updated_field_ids"] == set([field.id])


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
@patch("baserow_premium.fields.tasks.generate_ai_values_for_rows.delay")
def test_generate_ai_field_value_no_auto_update(patched_task, premium_data_fixture):
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

    assert patched_task.call_count == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
@patch("baserow_premium.fields.tasks.generate_ai_values_for_rows.delay")
def test_generate_ai_field_value_auto_update(patched_task, premium_data_fixture):
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

    assert patched_task.call_count == 1

    call_args = patched_task.call_args.args
    # field_id: int, row_ids: list[int]
    assert call_args == (
        user.id,
        ai_field.id,
        [r.id for r in rows],
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.field_ai
@override_settings(DEBUG=True)
@patch("baserow_premium.fields.tasks.generate_ai_values_for_rows.delay")
def test_generate_ai_field_value_auto_update_no_license_user(
    patched_task, premium_data_fixture
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
    assert patched_task.call_count == 0
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
