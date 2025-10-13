from unittest.mock import patch

import pytest

from baserow.contrib.database.fields.field_types import TextFieldType, UUIDFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.actions import (
    CreateRowsActionType,
    DeleteRowsActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.mark.django_db()
def test_local_baserow_upsert_row_handle_field_mapping_field_changes(
    data_fixture,
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[("My field", "number", {})],
    )
    field = table.field_set.get().specific
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )
    mapping = service.field_mappings.create(field=field, value=f"42")

    # Changing from a writable field to a read-only field deletes the mapping.
    FieldHandler().update_field(user, field, UUIDFieldType.type)
    assert service.field_mappings.filter(pk=mapping.pk).exists() is False


@pytest.mark.django_db()
def test_local_baserow_upsert_row_send_action_done_signal_when_creating_row(
    data_fixture,
):
    user, _ = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[("My field", "number", {})],
    )
    field = table.field_set.get().specific
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
    )

    service_type = service.get_type()
    service.field_mappings.create(field=field, value=f"42")

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with patch("baserow.core.action.signals.action_done.send") as send_mock:
        dispatch_data = service_type.dispatch_data(
            service, dispatch_values, dispatch_context
        )
        assert send_mock.call_count == 1

    assert dispatch_data["data"] is not None
    created_row = dispatch_data["data"]
    assert created_row.id is not None
    args = send_mock.call_args[1]
    assert args["action_type"].type == CreateRowsActionType.type
    assert args["action_params"]["row_ids"] == [created_row.id]


@pytest.mark.django_db()
def test_local_baserow_upsert_row_send_action_done_signal_when_updating_row(
    data_fixture,
):
    user, _ = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[("My field", "number", {})],
    )
    row = table.get_model().objects.create()
    field = table.field_set.get().specific
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=table,
        integration=integration,
        row_id=str(row.id),
    )

    service_type = service.get_type()
    service.field_mappings.create(field=field, value=f"42")

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with patch("baserow.core.action.signals.action_done.send") as send_mock:
        dispatch_data = service_type.dispatch_data(
            service, dispatch_values, dispatch_context
        )
        assert send_mock.call_count == 1

    assert dispatch_data["data"] is not None
    assert dispatch_data["data"].id == row.id
    args = send_mock.call_args[1]
    assert args["action_type"].type == UpdateRowsActionType.type
    assert args["action_params"]["row_ids"] == [row.id]


@pytest.mark.django_db()
def test_local_baserow_upsert_row_send_action_done_signal_when_deleting_row(
    data_fixture,
):
    user, _ = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[("My field", "number", {})],
    )
    row = table.get_model().objects.create()
    service = data_fixture.create_local_baserow_delete_row_service(
        table=table,
        integration=integration,
        row_id=str(row.id),
    )

    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with patch("baserow.core.action.signals.action_done.send") as send_mock:
        dispatch_data = service_type.dispatch_data(
            service, dispatch_values, dispatch_context
        )
        assert send_mock.call_count == 1

    assert dispatch_data["data"] is not None
    args = send_mock.call_args[1]
    assert args["action_type"].type == DeleteRowsActionType.type
    assert args["action_params"]["row_ids"] == [row.id]


@pytest.mark.django_db()
def test_local_baserow_service_filters_delete_when_field_type_changes_to_incompatible_type(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    link_field = data_fixture.create_link_row_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    service = data_fixture.create_local_baserow_list_rows_service(table=table)
    link_row_filter = data_fixture.create_local_baserow_table_service_filter(
        service=service, type="link_row_has", field=link_field, value="'1'", order=0
    )
    number_filter = data_fixture.create_local_baserow_table_service_filter(
        service=service, field=number_field, value="'25'", order=1
    )
    # Converting a `link_row` to a `text` field type will result in an
    # incompatible filter, so it'll be destroyed.
    FieldHandler().update_field(user, link_field, TextFieldType.type)
    assert not service.service_filters.filter(pk=link_row_filter.pk).exists()
    # However converting a `number` field to a `text` field type will result
    # in the filter staying compatible, so it's left intact.
    FieldHandler().update_field(user, number_field, TextFieldType.type)
    assert service.service_filters.filter(pk=number_filter.pk).exists()
