from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType

EDITOR_WEB_SOCKET_ID = "editor-web-socket-id"


def _restricted_view_calls(mock_broadcast_to_channel_group, view_id):
    """The (payload, ignore_web_socket_id) broadcast to a restricted view, in order."""

    group_name = f"restricted-view-{view_id}"
    return [
        (call.args[1], call.args[2])
        for call in mock_broadcast_to_channel_group.delay.mock_calls
        if call.args and call.args[0] == group_name
    ]


def _setup(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user(web_socket_id=EDITOR_WEB_SOCKET_ID)
    table = enterprise_data_fixture.create_database_table(user=user)
    field = enterprise_data_fixture.create_text_field(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        user,
        table=table,
        ownership_type=RestrictedViewOwnershipType.type,
        public=False,
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=field, type="equal", value="keep"
    )
    return user, table, field, restricted_view


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("web_socket_id", [EDITOR_WEB_SOCKET_ID, None])
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_rows_created_in_restricted_view_exclude_the_creator(
    mock_broadcast_to_channel_group, enterprise_data_fixture, batch, web_socket_id
):
    user, table, field, restricted_view = _setup(enterprise_data_fixture)
    user.web_socket_id = web_socket_id
    mock_broadcast_to_channel_group.reset_mock()

    with transaction.atomic():
        if batch:
            rows = (
                RowHandler()
                .create_rows(user, table, rows_values=[{field.db_column: "keep"}] * 2)
                .created_rows
            )
        else:
            rows = [
                RowHandler().create_row(user, table, values={field.db_column: "keep"})
            ]

    calls = _restricted_view_calls(mock_broadcast_to_channel_group, restricted_view.id)
    assert len(calls) == 1
    payload, ignore_web_socket_id = calls[0]
    assert payload["type"] == "rows_created"
    assert [row["id"] for row in payload["rows"]] == [row.id for row in rows]
    # The creator replaces its optimistic rows using the HTTP response. Receiving
    # this event first would insert them a second time under their persisted IDs.
    assert ignore_web_socket_id == web_socket_id


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("batch", [False, True])
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_rows_deleted_from_restricted_view_exclude_the_editor(
    mock_broadcast_to_channel_group, enterprise_data_fixture, batch
):
    user, table, field, restricted_view = _setup(enterprise_data_fixture)
    rows = (
        RowHandler()
        .create_rows(user, table, rows_values=[{field.db_column: "keep"}] * 2)
        .created_rows
    )
    mock_broadcast_to_channel_group.reset_mock()

    with transaction.atomic():
        if batch:
            RowHandler().delete_rows(user, table, row_ids=[row.id for row in rows])
        else:
            rows = rows[:1]
            RowHandler().delete_row(user, table, rows[0])

    calls = _restricted_view_calls(mock_broadcast_to_channel_group, restricted_view.id)
    assert len(calls) == 1
    payload, ignore_web_socket_id = calls[0]
    assert payload["type"] == "rows_deleted"
    assert payload["row_ids"] == [row.id for row in rows]
    assert ignore_web_socket_id == EDITOR_WEB_SOCKET_ID


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_edited_out_of_restricted_view_deletes_it_for_the_editor(
    mock_broadcast_to_channel_group, enterprise_data_fixture
):
    user, table, field, restricted_view = _setup(enterprise_data_fixture)
    row = RowHandler().create_row(user, table, values={field.db_column: "keep"})

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(user, table, [{"id": row.id, field.db_column: "drop"}])

    calls = _restricted_view_calls(mock_broadcast_to_channel_group, restricted_view.id)
    assert len(calls) == 1
    payload, ignore_web_socket_id = calls[0]
    assert payload["type"] == "rows_deleted"
    assert payload["row_ids"] == [row.id]
    assert ignore_web_socket_id is None


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_edited_into_restricted_view_creates_it_for_the_editor(
    mock_broadcast_to_channel_group, enterprise_data_fixture
):
    user, table, field, restricted_view = _setup(enterprise_data_fixture)
    row = RowHandler().create_row(user, table, values={field.db_column: "drop"})

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(user, table, [{"id": row.id, field.db_column: "keep"}])

    calls = _restricted_view_calls(mock_broadcast_to_channel_group, restricted_view.id)
    assert len(calls) == 1
    payload, ignore_web_socket_id = calls[0]
    assert payload["type"] == "rows_created"
    assert [r["id"] for r in payload["rows"]] == [row.id]
    assert ignore_web_socket_id is None


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_updated_within_restricted_view_still_excludes_the_editor(
    mock_broadcast_to_channel_group, enterprise_data_fixture
):
    user, table, field, restricted_view = _setup(enterprise_data_fixture)
    row = RowHandler().create_row(user, table, values={field.db_column: "keep"})

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(user, table, [{"id": row.id, field.db_column: "keep"}])

    calls = _restricted_view_calls(mock_broadcast_to_channel_group, restricted_view.id)
    assert len(calls) == 1
    payload, ignore_web_socket_id = calls[0]
    assert payload["type"] == "rows_updated"
    assert ignore_web_socket_id == EDITOR_WEB_SOCKET_ID
