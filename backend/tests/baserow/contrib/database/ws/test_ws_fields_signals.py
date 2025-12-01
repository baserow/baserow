from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_field_created(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = FieldHandler().create_field(
        user=user, table=table, type_name="text", name="Grid"
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "field_created"
    assert args[0][1]["field"]["id"] == field.id
    assert args[0][1]["related_fields"] == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_field_restored(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user)
    data_fixture.create_grid_view(user, table=table)
    field = data_fixture.create_text_field(user=user, table=table)
    view_sort = data_fixture.create_view_sort(user, field=field)
    view_group_by = data_fixture.create_view_group_by(user, field=field)
    view_filter = data_fixture.create_view_filter(user, field=field)
    FieldHandler().delete_field(user, field)
    TrashHandler.restore_item(user, "field", field.id)

    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{field.table.id}"
    assert args[0][1]["type"] == "field_restored"
    assert args[0][1]["field"]["id"] == field.id, args[0]
    sortings = args[0][1]["field"]["sortings"]
    filters = args[0][1]["field"]["filters"]
    group_bys = args[0][1]["field"]["group_bys"]
    assert len(filters) == 1
    assert filters[0]["id"] == view_filter.id
    assert len(sortings) == 1
    assert sortings[0]["id"] == view_sort.id
    assert len(group_bys) == 1
    assert group_bys[0]["id"] == view_group_by.id
    assert args[0][1]["related_fields"] == []


@pytest.mark.django_db(transaction=True)
def test_field_restored_doesnt_do_n_plus_some_queries(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user)
    data_fixture.create_grid_view(user, table=table)
    field = data_fixture.create_text_field(user=user, table=table)
    data_fixture.create_view_sort(user, field=field)
    data_fixture.create_view_filter(user, field=field)
    FieldHandler().delete_field(user, field)

    with CaptureQueriesContext(connection) as captured:
        TrashHandler.restore_item(user, "field", field.id)

    FieldHandler().delete_field(user, field)
    data_fixture.create_view_sort(user, field=field)
    data_fixture.create_view_filter(user, field=field)

    with CaptureQueriesContext(connection) as captured2:
        # We shouldn't be running more queries if there are simply more view
        # sorts/filters
        TrashHandler.restore_item(user, "field", field.id)

    assert len(captured2.captured_queries) <= len(captured.captured_queries), (
        "Restoring a field should not result in more queries if there are more view "
        "sorts/filters"
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_field_updated(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    field = data_fixture.create_text_field(user=user)
    FieldHandler().update_field(user=user, field=field, name="field")

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{field.table.id}"
    assert args[0][1]["type"] == "field_updated"
    assert args[0][1]["field_id"] == field.id
    assert args[0][1]["field"]["id"] == field.id
    assert args[0][1]["related_fields"] == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_field_deleted(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    field = data_fixture.create_text_field(user=user)
    field_id = field.id
    table_id = field.table_id
    FieldHandler().delete_field(user=user, field=field)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{field.table.id}"
    assert args[0][1]["type"] == "field_deleted"
    assert args[0][1]["field_id"] == field_id
    assert args[0][1]["table_id"] == table_id
    assert args[0][1]["related_fields"] == []
