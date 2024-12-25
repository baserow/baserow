from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.webhooks.registries import webhook_event_type_registry
from baserow.contrib.database.ws.rows.signals import serialize_rows_values
from baserow.test_utils.helpers import AnyStr


@pytest.mark.django_db()
def test_rows_created_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, primary=True, name="Test 1")

    model = table.get_model()
    row = model.objects.create()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("rows.created").get_payload(
        event_id="1", webhook=webhook, model=model, table=table, rows=[row]
    )
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "event_id": "1",
        "event_type": "rows.created",
        "items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"field_{field.id}": None,
            }
        ],
    }

    webhook.use_user_field_names = True
    webhook.save()
    payload = webhook_event_type_registry.get("rows.created").get_payload(
        event_id="1", webhook=webhook, model=model, table=table, rows=[row]
    )
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "event_id": "1",
        "event_type": "rows.created",
        "items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                "Test 1": None,
            }
        ],
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_created_event_type_without_webhook_event(mock_call_webhook, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    webhook = data_fixture.create_table_webhook(
        user=user,
        table=table,
        url="http://localhost/",
        include_all_events=False,
        events=["rows.created"],
        headers={"Baserow-header-1": "Value 1"},
    )

    RowHandler().create_rows(
        user=user, table=table, rows_values=[{}], send_webhook_events=False
    )

    mock_call_webhook.delay.assert_not_called()


@pytest.mark.django_db()
def test_rows_created_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, primary=True, name="Test 1")

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("rows.created")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "event_id": "1",
        "event_type": "rows.created",
        "items": [
            {
                "id": 0,
                "order": "0.00000000000000000000",
                f"field_{field.id}": None,
            }
        ],
    }


@pytest.mark.django_db()
def test_rows_updated_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(database=table.database)

    text_field = data_fixture.create_text_field(
        table=table, primary=True, name="Test 1"
    )
    table_2_primary_field = data_fixture.create_text_field(
        table=table_2, name="Primary Field", primary=True
    )

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Link",
        link_row_table=table_2,
    )

    lookup_model = table_2.get_model()
    i1 = lookup_model.objects.create(
        **{f"field_{table_2_primary_field.id}": "Lookup 1"}
    )

    grid = data_fixture.create_grid_view(table=table)
    data_fixture.create_grid_view_field_option(grid, link_row_field, hidden=False)

    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "Old Test value"})
    getattr(row, f"field_{link_row_field.id}").add(i1.id)

    before_return = {
        serialize_rows_values: serialize_rows_values(
            None, [row], user, table, model, [text_field.id]
        )
    }

    row = RowHandler().update_row_by_id(
        user=user,
        table=table,
        row_id=row.id,
        values={f"field_{text_field.id}": "New Test value"},
    )
    row.refresh_from_db()

    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("rows.updated").get_payload(
        event_id="1",
        webhook=webhook,
        model=model,
        table=table,
        rows=[row],
        before_return=before_return,
        updated_field_ids=[],
    )
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "event_id": "1",
        "event_type": "rows.updated",
        "items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"field_{text_field.id}": "New Test value",
                f"field_{link_row_field.id}": [
                    {"id": 1, "value": "Lookup 1", "order": AnyStr()}
                ],
            }
        ],
        "old_items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"field_{text_field.id}": "Old Test value",
                f"field_{link_row_field.id}": [
                    {"id": 1, "value": "Lookup 1", "order": AnyStr()}
                ],
            }
        ],
    }

    webhook.use_user_field_names = True
    webhook.save()
    payload = webhook_event_type_registry.get("rows.updated").get_payload(
        event_id="1",
        webhook=webhook,
        model=model,
        table=table,
        rows=[row],
        before_return=before_return,
        updated_field_ids=[],
    )
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "event_id": "1",
        "event_type": "rows.updated",
        "items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"{text_field.name}": "New Test value",
                f"{link_row_field.name}": [
                    {"id": 1, "value": "Lookup 1", "order": AnyStr()}
                ],
            }
        ],
        "old_items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"{text_field.name}": "Old Test value",
                f"{link_row_field.name}": [
                    {"id": 1, "value": "Lookup 1", "order": AnyStr()}
                ],
            }
        ],
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_updated_event_type_skip_not_updated_fields(
    mock_call_webhook, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    model = table.get_model()
    row = model.objects.create()

    RowHandler().update_rows(
        user,
        table,
        [
            {"id": row.id},
        ],
        rows_to_update=[row],
        send_webhook_events=False,
    )

    mock_call_webhook.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_updated_event_type_without_webhook_event(mock_call_webhook, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field_1 = data_fixture.create_text_field(table=table, primary=True, name="Test 1")
    field_2 = data_fixture.create_text_field(table=table, primary=True, name="Test 1")

    webhook = data_fixture.create_table_webhook(
        user=user,
        table=table,
        url="http://localhost/",
        include_all_events=False,
        events=["rows.updated"],
        headers={"Baserow-header-1": "Value 1"},
    )

    updated_event = webhook.events.all().first()
    updated_event.fields.set([field_1.id])

    model = table.get_model()
    row = model.objects.create(
        **{f"field_{field_1.id}": "Unchanged", f"field_{field_2.id}": "Unchanged"},
    )

    with transaction.atomic():
        RowHandler().update_row_by_id(
            user=user,
            table=table,
            row_id=row.id,
            values={},
        )
    mock_call_webhook.delay.assert_not_called()

    with transaction.atomic():
        RowHandler().update_row_by_id(
            user=user,
            table=table,
            row_id=row.id,
            values={f"field_{field_2.id}": "Changed"},
        )
    mock_call_webhook.delay.assert_not_called()

    with transaction.atomic():
        RowHandler().update_row_by_id(
            user=user,
            table=table,
            row_id=row.id,
            values={f"field_{field_1.id}": "Changed"},
        )
    mock_call_webhook.delay.assert_called_once()


@pytest.mark.django_db()
def test_rows_updated_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, primary=True, name="Test 1")

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("rows.updated")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "event_id": "1",
        "event_type": "rows.updated",
        "items": [
            {
                "id": 0,
                "order": "0.00000000000000000000",
                f"field_{field.id}": None,
            }
        ],
        "old_items": [
            {
                "id": 0,
                "order": "0.00000000000000000000",
                f"field_{field.id}": None,
            }
        ],
    }


@pytest.mark.django_db()
def test_rows_deleted_event_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, primary=True, name="Test 1")

    model = table.get_model()
    row = model.objects.create()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("rows.deleted").get_payload(
        event_id="1",
        webhook=webhook,
        model=model,
        table=table,
        rows=[row],
    )

    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "event_id": "1",
        "event_type": "rows.deleted",
        "row_ids": [row.id],
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_deleted_event_type_without_webhook_event(mock_call_webhook, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    webhook = data_fixture.create_table_webhook(
        user=user,
        table=table,
        url="http://localhost/",
        include_all_events=False,
        events=["rows.deleted"],
        headers={"Baserow-header-1": "Value 1"},
    )
    model = table.get_model()
    row = model.objects.create()

    RowHandler().delete_rows(user, table, row_ids=[row.id], send_webhook_events=False)

    mock_call_webhook.delay.assert_not_called()


@pytest.mark.django_db()
def test_rows_deleted_event_type_test_payload(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, primary=True, name="Test 1")

    model = table.get_model()
    webhook = data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("rows.deleted")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "event_id": "1",
        "event_type": "rows.deleted",
        "row_ids": [0],
    }
