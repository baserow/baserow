from collections import OrderedDict
from typing import Any, Dict, List
from unittest.mock import call, patch

from django.db import transaction

import pytest
from freezegun import freeze_time
from rest_framework import serializers
from rest_framework.fields import Field

from baserow.contrib.database.rows import signals as row_signals
from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.registries import (
    RowMetadataType,
    row_metadata_registry,
)
from baserow.test_utils.helpers import AnyInt, register_instance_temporarily


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_created(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    row = RowHandler().create_row(
        user=user, table=table, values={f"field_{field.id}": "Test"}
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_created"
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["rows"][0]["id"] == row.id
    assert args[0][1]["before_row_id"] is None
    assert args[0][1]["rows"][0][f"field_{field.id}"] == "Test"
    assert args[0][1]["metadata"] == {}

    row_2 = RowHandler().create_row(
        user=user, table=table, before_row=row, values={f"field_{field.id}": "Test2"}
    )
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_created"
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["rows"][0]["id"] == row_2.id
    assert args[0][1]["before_row_id"] == row.id
    assert args[0][1]["rows"][0][f"field_{field.id}"] == "Test2"
    assert args[0][1]["metadata"] == {}


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_created_without_sending_realtime_update(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    RowHandler().create_rows(
        user=user,
        table=table,
        rows_values=[{f"field_{field.id}": "Test"}],
        send_realtime_update=False,
    )
    mock_broadcast_to_channel_group.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_created_with_metadata(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    with register_instance_temporarily(
        row_metadata_registry, test_populates_with_row_id_metadata()
    ):
        row = RowHandler().create_row(
            user=user, table=table, values={f"field_{field.id}": "Test"}
        )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_created"
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["rows"][0]["id"] == row.id
    assert args[0][1]["before_row_id"] is None
    assert args[0][1]["rows"][0][f"field_{field.id}"] == "Test"
    assert args[0][1]["metadata"] == {1: {"row_id": row.id}}


def test_populates_with_row_id_metadata():
    class RowIdMetadata(RowMetadataType):
        type = "row_id"

        def generate_metadata_for_rows(
            self, user, table, row_ids: List[int]
        ) -> Dict[int, Any]:
            return {row_id: row_id for row_id in row_ids}

        def get_example_serializer_field(self) -> Field:
            return serializers.CharField()

    return RowIdMetadata()


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_updated(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    row = table.get_model().objects.create()
    RowHandler().update_row_by_id(
        user=user, table=table, row_id=row.id, values={f"field_{field.id}": "Test"}
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_updated"
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["rows_before_update"][0]["id"] == row.id
    assert args[0][1]["rows_before_update"][0][f"field_{field.id}"] is None
    assert args[0][1]["rows_before_update"][0][f"field_{field_2.id}"] is None
    assert args[0][1]["rows"][0]["id"] == row.id
    assert args[0][1]["rows"][0][f"field_{field.id}"] == "Test"
    assert args[0][1]["rows"][0][f"field_{field_2.id}"] is None
    assert args[0][1]["metadata"] == {}

    row.refresh_from_db()
    setattr(row, f"field_{field_2.id}", "Second")
    row.save()
    RowHandler().update_row_by_id(
        user=user, table=table, row_id=row.id, values={f"field_{field.id}": "First"}
    )

    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_updated"
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["rows"][0]["id"] == row.id
    assert args[0][1]["rows"][0][f"field_{field.id}"] == "First"
    assert args[0][1]["rows"][0][f"field_{field_2.id}"] == "Second"
    assert args[0][1]["metadata"] == {}


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_updated_without_sending_realtime_update(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    row = table.get_model().objects.create()
    RowHandler().update_rows(
        user,
        table,
        [
            {"id": row.id, f"field_{field.id}": "test"},
        ],
        rows_to_update=[row],
        send_realtime_update=False,
    )

    mock_broadcast_to_channel_group.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_updated_with_metadata(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    row = table.get_model().objects.create()

    with register_instance_temporarily(
        row_metadata_registry, test_populates_with_row_id_metadata()
    ):
        RowHandler().update_row_by_id(
            user=user, table=table, row_id=row.id, values={f"field_{field.id}": "Test"}
        )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_updated"
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["rows_before_update"][0]["id"] == row.id
    assert args[0][1]["rows_before_update"][0][f"field_{field.id}"] is None
    assert args[0][1]["rows_before_update"][0][f"field_{field_2.id}"] is None
    assert args[0][1]["rows"][0]["id"] == row.id
    assert args[0][1]["rows"][0][f"field_{field.id}"] == "Test"
    assert args[0][1]["rows"][0][f"field_{field_2.id}"] is None
    assert args[0][1]["metadata"] == {1: {"row_id": row.id}}


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_deleted(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(
        table=table, name="Name", text_default="Test"
    )
    row = table.get_model().objects.create(**{f"field_{field.id}": "Value"})
    row_id = row.id
    RowHandler().delete_row_by_id(user=user, table=table, row_id=row_id)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_deleted"
    assert args[0][1]["row_ids"] == [row_id]
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["rows"][0]["id"] == row_id
    assert args[0][1]["rows"][0][f"field_{field.id}"] == "Value"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_deleted_without_sending_realtime_update(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    row = table.get_model().objects.create()
    RowHandler().delete_rows(user, table, row_ids=[row.id], send_realtime_update=False)

    mock_broadcast_to_channel_group.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_row_orders_recalculated(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    RowHandler().recalculate_row_orders(table=table)

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "row_orders_recalculated"
    assert args[0][1]["table_id"] == table.id


@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@patch("baserow.ws.registries.broadcast_many_to_channel_group")
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_rows_history_updated(
    mock_broadcast_channel_group, mock_broadcast_many_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    model = table.get_model()

    row1 = model.objects.create(**{f"field_{field.id}": "row 1"})
    row2 = model.objects.create(**{f"field_{field.id}": "row 2"})

    rows_values = [
        {
            "id": row1.id,
            f"field_{field.id}": "row 1 updated",
        },
        {
            "id": row2.id,
            f"field_{field.id}": "row 2 updated",
        },
    ]

    with freeze_time("2023-03-30 00:00:00"), transaction.atomic():
        UpdateRowsActionType.do(user, table, rows_values, model)

    table_and_row_broadcast_calls = [
        call.delay(
            f"table-{table.id}",
            {
                "type": "rows_updated",
                "table_id": table.id,
                "rows_before_update": [
                    OrderedDict(
                        [
                            ("id", row1.id),
                            ("order", "1.00000000000000000000"),
                            (f"field_{field.id}", "row 1"),
                        ]
                    ),
                    OrderedDict(
                        [
                            ("id", row2.id),
                            ("order", "1.00000000000000000000"),
                            (f"field_{field.id}", "row 2"),
                        ]
                    ),
                ],
                "rows": [
                    OrderedDict(
                        [
                            ("id", row1.id),
                            ("order", "1.00000000000000000000"),
                            (f"field_{field.id}", "row 1 updated"),
                        ]
                    ),
                    OrderedDict(
                        [
                            ("id", row2.id),
                            ("order", "1.00000000000000000000"),
                            (f"field_{field.id}", "row 2 updated"),
                        ]
                    ),
                ],
                "metadata": {},
                "updated_field_ids": [field.id],
            },
            None,
            None,
        ),
    ]

    row_history_many_broadcast_calls = [
        call.delay(
            [
                (
                    f"table-{table.id}-row-{row1.id}",
                    {
                        "type": "row_history_updated",
                        "row_history_entry": {
                            "id": AnyInt(),
                            "action_type": "update_rows",
                            "action_command_type": "DO",
                            "user": OrderedDict(
                                [("id", user.id), ("name", user.first_name)]
                            ),
                            "timestamp": "2023-03-30T00:00:00Z",
                            "before": {f"field_{field.id}": "row 1"},
                            "after": {f"field_{field.id}": "row 1 updated"},
                            "fields_metadata": {
                                f"field_{field.id}": {"id": field.id, "type": "text"}
                            },
                        },
                        "table_id": table.id,
                        "row_id": row1.id,
                    },
                ),
                (
                    f"table-{table.id}-row-{row2.id}",
                    {
                        "type": "row_history_updated",
                        "row_history_entry": {
                            "id": AnyInt(),
                            "action_type": "update_rows",
                            "action_command_type": "DO",
                            "user": OrderedDict(
                                [("id", user.id), ("name", user.first_name)]
                            ),
                            "timestamp": "2023-03-30T00:00:00Z",
                            "before": {f"field_{field.id}": "row 2"},
                            "after": {f"field_{field.id}": "row 2 updated"},
                            "fields_metadata": {
                                f"field_{field.id}": {"id": field.id, "type": "text"}
                            },
                        },
                        "table_id": table.id,
                        "row_id": row2.id,
                    },
                ),
            ],
            # limit to channel/user - empty here
            None,
            None,
        )
    ]

    assert (
        mock_broadcast_many_channel_group.mock_calls == row_history_many_broadcast_calls
    )
    assert mock_broadcast_channel_group.mock_calls == table_and_row_broadcast_calls


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_rows_ai_values_generation_error(mock_broadcast_to_channel_group, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    model = table.get_model()
    row1 = model.objects.create()
    row2 = model.objects.create()

    row_signals.rows_ai_values_generation_error.send(
        sender=None,
        user=user,
        rows=[row1, row2],
        field=field,
        table=table,
        error_message="Test error message",
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_ai_values_generation_error"
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["field_id"] == field.id
    assert args[0][1]["row_ids"] == [row1.id, row2.id]
    assert args[0][1]["error"] == "Test error message"
    assert args[0][2] is None


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_rows_ai_values_generation_error_with_empty_rows(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    row_signals.rows_ai_values_generation_error.send(
        sender=None,
        user=user,
        rows=[],
        field=field,
        table=table,
        error_message="Model not available",
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "rows_ai_values_generation_error"
    assert args[0][1]["table_id"] == table.id
    assert args[0][1]["field_id"] == field.id
    assert args[0][1]["row_ids"] == []
    assert args[0][1]["error"] == "Model not available"
    assert args[0][2] is None
