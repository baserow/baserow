from unittest.mock import AsyncMock, patch

from django.db import transaction
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.fields.dependencies.update_collector import (
    DependantRowsUpdate,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.signals import dependant_rows_updated
from baserow.contrib.database.ws.rows.tasks import broadcast_dependant_rows_updated


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.rows.signals.broadcast_dependant_rows_updated")
def test_updating_a_row_broadcasts_dependant_rows_to_the_linked_table(
    mock_broadcast_task, data_fixture
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "b1"}])
        .created_rows[0]
    )
    row_a1 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])
        .created_rows[0]
    )
    mock_broadcast_task.reset_mock()

    with transaction.atomic():
        RowHandler().update_rows(
            user, table_b, [{"id": row_b1.id, primary_b.db_column: "renamed"}]
        )

    mock_broadcast_task.delay.assert_called_once_with(
        table_id=table_a.id,
        row_ids=[row_a1.id],
        updated_field_ids=[link_a_b.id],
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.table.signals.broadcast_to_permitted_users")
@patch("baserow.contrib.database.ws.rows.signals.broadcast_dependant_rows_updated")
def test_requires_refresh_sends_a_force_table_refresh(
    mock_broadcast_task, mock_broadcast_to_permitted_users, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    dependant_rows_updated.send(
        None,
        user=user,
        table=table,
        dependant_rows_updates=[
            DependantRowsUpdate(
                table=table, row_ids=[], field_ids=[1], requires_refresh=True
            )
        ],
        send_realtime_update=True,
    )

    mock_broadcast_task.delay.assert_not_called()
    mock_broadcast_to_permitted_users.delay.assert_called_once()
    payload = mock_broadcast_to_permitted_users.delay.call_args[0][4]
    assert payload["type"] == "table_updated"
    assert payload["force_table_refresh"] is True


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.table.signals.broadcast_to_permitted_users")
@patch("baserow.contrib.database.ws.rows.signals.broadcast_dependant_rows_updated")
def test_every_affected_table_under_the_limit_is_broadcast_exactly(
    mock_broadcast_task, mock_broadcast_to_permitted_users, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    tables = [data_fixture.create_database_table(database=database) for _ in range(12)]

    dependant_rows_updated.send(
        None,
        user=user,
        table=tables[0],
        dependant_rows_updates=[
            DependantRowsUpdate(
                table=table, row_ids=[1], field_ids=[1], requires_refresh=False
            )
            for table in tables
        ],
        send_realtime_update=True,
    )

    # A wide fan-out sends an invisible exact broadcast per table and never a
    # disruptive refresh; only the per-table row limit can force a refresh.
    assert mock_broadcast_task.delay.call_count == 12
    assert mock_broadcast_to_permitted_users.delay.call_count == 0


@pytest.mark.django_db(transaction=True)
@override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=0)
@patch("baserow.contrib.database.ws.table.signals.broadcast_to_permitted_users")
@patch("baserow.contrib.database.ws.rows.signals.broadcast_dependant_rows_updated")
def test_nothing_is_sent_when_disabled(
    mock_broadcast_task, mock_broadcast_to_permitted_users, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    dependant_rows_updated.send(
        None,
        user=user,
        table=table,
        dependant_rows_updates=[
            DependantRowsUpdate(
                table=table, row_ids=[1], field_ids=[1], requires_refresh=False
            ),
            DependantRowsUpdate(
                table=table, row_ids=[], field_ids=[], requires_refresh=True
            ),
        ],
        send_realtime_update=True,
    )

    mock_broadcast_task.delay.assert_not_called()
    mock_broadcast_to_permitted_users.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.table.signals.broadcast_to_permitted_users")
@patch("baserow.contrib.database.ws.rows.signals.broadcast_dependant_rows_updated")
def test_nothing_is_sent_without_realtime_update(
    mock_broadcast_task, mock_broadcast_to_permitted_users, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    dependant_rows_updated.send(
        None,
        user=user,
        table=table,
        dependant_rows_updates=[
            DependantRowsUpdate(
                table=table, row_ids=[1], field_ids=[1], requires_refresh=False
            )
        ],
        send_realtime_update=False,
    )

    mock_broadcast_task.delay.assert_not_called()
    mock_broadcast_to_permitted_users.delay.assert_not_called()


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.ws.rows.tasks.send_messages_to_channel_group",
    new_callable=AsyncMock,
)
def test_broadcast_task_sends_a_rows_updated_payload(mock_send, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    model = table.get_model()
    row_1 = model.objects.create(**{field.db_column: "a"})
    row_2 = model.objects.create(**{field.db_column: "b"})

    broadcast_dependant_rows_updated(
        table_id=table.id,
        row_ids=[row_1.id, row_2.id],
        updated_field_ids=[field.id],
    )

    mock_send.assert_called_once()
    message = mock_send.call_args[0][1]
    assert message.channel_group_name == f"table-{table.id}"
    payload = message.message["payload"]
    assert payload["type"] == "rows_updated"
    assert payload["table_id"] == table.id
    assert payload["updated_field_ids"] == [field.id]
    assert [row["id"] for row in payload["rows"]] == [row_1.id, row_2.id]
    assert payload["rows"][0][field.db_column] == "a"
    assert payload["rows_before_update"] == [{"id": row_1.id}, {"id": row_2.id}]
    assert message.message["ignore_web_socket_id"] is None


@pytest.mark.django_db
@patch(
    "baserow.contrib.database.ws.rows.tasks.send_messages_to_channel_group",
    new_callable=AsyncMock,
)
def test_broadcast_task_skips_trashed_rows_and_missing_tables(mock_send, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    model = table.get_model()
    row_1 = model.objects.create(**{field.db_column: "a"})
    row_2 = model.objects.create(**{field.db_column: "b"}, trashed=True)

    broadcast_dependant_rows_updated(
        table_id=table.id, row_ids=[row_1.id, row_2.id], updated_field_ids=[field.id]
    )
    payload = mock_send.call_args[0][1].message["payload"]
    assert [row["id"] for row in payload["rows"]] == [row_1.id]

    mock_send.reset_mock()
    broadcast_dependant_rows_updated(
        table_id=table.id, row_ids=[row_2.id], updated_field_ids=[field.id]
    )
    mock_send.assert_not_called()

    broadcast_dependant_rows_updated(
        table_id=0, row_ids=[row_1.id], updated_field_ids=[field.id]
    )
    mock_send.assert_not_called()
