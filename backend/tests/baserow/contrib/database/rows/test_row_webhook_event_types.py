from unittest.mock import MagicMock, patch

from django.db import connection, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.webhook_event_types import RowsUpdatedEventType
from baserow.contrib.database.webhooks.handler import WebhookHandler
from baserow.contrib.database.webhooks.models import TableWebhook
from baserow.contrib.database.webhooks.registries import webhook_event_type_registry
from baserow.contrib.database.ws.rows.signals import serialize_rows_values
from baserow.core.redis import WebhookRedisQueue
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
        "webhook_id": webhook.id,
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
        "webhook_id": webhook.id,
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
        "webhook_id": webhook.id,
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
        "webhook_id": webhook.id,
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
        "webhook_id": webhook.id,
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
        "webhook_id": webhook.id,
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
        "webhook_id": webhook.id,
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
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "rows.deleted",
        "row_ids": [0],
    }


@pytest.mark.django_db()
def test_get_filters_for_related_webhook_to_call(data_fixture):
    """
    Make sure webhooks are triggers only for the right tables,
    when the configuration requires it and there are changes in the
    link row field values.
    """

    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    table_c = data_fixture.create_database_table(user=user)
    table_d = data_fixture.create_database_table()
    primary_a = table_a.get_primary_field()
    primary_b = table_b.get_primary_field()

    webhook_1 = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        include_all_events=True,
    )
    webhook_2 = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        include_all_events=False,
        events=["rows.created"],
    )
    webhook_3 = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        include_all_events=False,
        events=["rows.updated"],
    )
    webhook_4 = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        include_all_events=False,
        events=["rows.deleted"],
    )
    webhook_5 = WebhookHandler().create_table_webhook(
        user=user,
        table=table_b,
        request_method="POST",
        url="http://localhost",
        include_all_events=False,
        events=["rows.updated"],
        event_config=[{"event_type": "rows.updated", "fields": [primary_b.id]}],
    )
    webhook_6 = WebhookHandler().create_table_webhook(
        user=user,
        table=table_b,
        request_method="POST",
        url="http://localhost",
        include_all_events=False,
        events=["rows.updated"],
        event_config=[
            {
                "event_type": "rows.updated",
                "fields": [link_a_to_b.link_row_related_field_id],
            }
        ],
    )
    webhook_7 = data_fixture.create_table_webhook(
        table=table_c,
        request_method="POST",
        url="http://localhost",
        include_all_events=True,
    )
    webhook_7 = data_fixture.create_table_webhook(
        table=table_d,
        request_method="POST",
        url="http://localhost",
        include_all_events=True,
    )

    event_type: RowsUpdatedEventType = webhook_event_type_registry.get("rows.updated")
    model_a = table_a.get_model()

    rows_a_without_changes_in_b = (
        RowHandler()
        .force_create_rows(
            user=user,
            table=table_a,
            rows_values=[{primary_a.db_column: "a1"}, {}],
        )
        .created_rows
    )

    q = event_type.get_filters_for_related_webhook_to_call(
        model_a, rows_a_without_changes_in_b
    )
    webhooks_to_trigger = (
        TableWebhook.objects.filter(q).order_by("id").values_list("id", flat=True)
    )
    # no webhooks should be triggered since there are no changes in table_b
    assert list(webhooks_to_trigger) == []

    row_b1, row_b2 = (
        RowHandler()
        .force_create_rows(user=user, table=table_b, rows_values=[{}, {}])
        .created_rows
    )

    rows_a_with_changes = (
        RowHandler()
        .force_create_rows(
            user=user,
            table=table_a,
            rows_values=[
                {link_a_to_b.db_column: [row_b1.id, row_b2.id]},
            ],
        )
        .created_rows
    )

    q = event_type.get_filters_for_related_webhook_to_call(model_a, rows_a_with_changes)
    webhooks_to_trigger = (
        TableWebhook.objects.filter(q).order_by("id").values_list("id", flat=True)
    )
    assert list(webhooks_to_trigger) == [
        webhook_1.id,  # include_all_events=True
        webhook_3.id,  # rows.updated without specific fields
        webhook_6.id,  # rows.updated with link field in the list
    ]


@pytest.mark.django_db(transaction=True)
def test_rows_updated_event_type_can_trigger_webhooks_in_linked_tables_on_rows_created(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)

    row_b1, row_b2, row_b3 = (
        RowHandler().force_create_rows(user, table_b, [{}, {}, {}]).created_rows
    )

    webhook = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
        include_all_events=True,
    )

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as p:
        # It's not called without changes to link row values in table_b
        RowHandler().force_create_rows(user, table_a, [{}])

        assert p.called is False

        # Only when creating rows in table_a updates rows in table_b
        RowHandler().force_create_rows(
            user,
            table_a,
            [{link_a_to_b.db_column: [row_b1.id, row_b2.id, row_b3.id]}],
        )

        assert p.called
        assert p.call_args[1]["payload"] == {
            "table_id": table_b.id,
            "database_id": table_b.database_id,
            "workspace_id": table_b.database.workspace_id,
            "webhook_id": webhook.id,
            "event_id": AnyStr(),
            "event_type": "rows.updated",
            # Send only the row ids to the task
            "item_ids": [row_b1.id, row_b2.id, row_b3.id],
            "total_count": 3,
        }


@pytest.mark.django_db(transaction=True)
def test_rows_updated_event_type_can_trigger_webhooks_in_linked_tables_on_rows_updated(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    primary_a = table_a.get_primary_field()

    row_b1, row_b2, row_b3 = (
        RowHandler().force_create_rows(user, table_b, [{}, {}, {}]).created_rows
    )

    (row_a1,) = RowHandler().force_create_rows(user, table_a, [{}]).created_rows

    webhook = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
        include_all_events=True,
    )

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as p:
        # It's not called without changes to link row values in table_b
        with transaction.atomic():
            RowHandler().force_update_rows(
                user,
                table_a,
                [{"id": row_a1.id, primary_a.db_column: "a1"}],
            )

        assert p.called is False

        # Only when updating rows in table_a updates rows in table_b
        with transaction.atomic():
            RowHandler().force_update_rows(
                user,
                table_a,
                [
                    {
                        "id": row_a1.id,
                        link_a_to_b.db_column: [row_b1.id, row_b2.id, row_b3.id],
                    }
                ],
            )

        assert p.call_count == 1
        assert p.call_args[1]["payload"] == {
            "table_id": table_b.id,
            "database_id": table_b.database_id,
            "workspace_id": table_b.database.workspace_id,
            "webhook_id": webhook.id,
            "event_id": AnyStr(),
            "event_type": "rows.updated",
            # Send only the row ids to the task
            "item_ids": [row_b1.id, row_b2.id, row_b3.id],
            "total_count": 3,
        }


@pytest.mark.django_db(transaction=True)
def test_rows_updated_event_type_can_trigger_webhooks_in_linked_tables_on_rows_deleted(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    primary_a = table_a.get_primary_field()

    row_b1, row_b2, row_b3 = (
        RowHandler().force_create_rows(user, table_b, [{}, {}, {}]).created_rows
    )

    row_a1, row_a2 = (
        RowHandler()
        .force_create_rows(
            user,
            table_a,
            [{}, {link_a_to_b.db_column: [row_b1.id, row_b2.id, row_b3.id]}],
        )
        .created_rows
    )

    webhook = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
        include_all_events=True,
    )

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as p:
        # It's not called without changes to link row values in table_b
        RowHandler().force_delete_rows(user, table_a, [row_a1.id])

        assert p.called is False

        # Only when updating rows in table_a updates rows in table_b
        RowHandler().force_delete_rows(user, table_a, [row_a2.id])

        assert p.call_count == 1
        assert p.call_args[1]["payload"] == {
            "table_id": table_b.id,
            "database_id": table_b.database_id,
            "workspace_id": table_b.database.workspace_id,
            "webhook_id": webhook.id,
            "event_id": AnyStr(),
            "event_type": "rows.updated",
            # Send only the row ids to the task
            "item_ids": [row_b1.id, row_b2.id, row_b3.id],
            "total_count": 3,
        }


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_rows_updated_event_type_payload_for_linked_tables(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    primary_a = table_a.get_primary_field()
    primary_b = table_b.get_primary_field()
    link_b_to_a = link_a_to_b.link_row_related_field

    row_b1, row_b2, row_b3 = (
        RowHandler().force_create_rows(user, table_b, [{}, {}, {}]).created_rows
    )

    webhook = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
        include_all_events=True,
    )

    # Webhook in table b is trigger when creating rows in table a
    # and linking them to rows in table b
    with patch(
        "baserow.contrib.database.webhooks.tasks.make_request_and_save_result",
    ) as p:
        (row_a1,) = (
            RowHandler()
            .force_create_rows(
                user,
                table_a,
                [
                    {
                        primary_a.db_column: "a1",
                        link_a_to_b.db_column: [row_b1.id, row_b2.id, row_b3.id],
                    }
                ],
            )
            .created_rows
        )

        assert p.call_count == 1
        assert p.call_args.args[6] == {
            "table_id": table_b.id,
            "database_id": table_b.database_id,
            "workspace_id": table_b.database.workspace_id,
            "webhook_id": webhook.id,
            "event_id": AnyStr(),
            "event_type": "rows.updated",
            # Send all the rows data
            "items": [
                {
                    "id": row_b1.id,
                    "order": AnyStr(),
                    primary_b.db_column: None,
                    link_b_to_a.db_column: [
                        {"id": row_a1.id, "value": "a1", "order": AnyStr()}
                    ],
                },
                {
                    "id": row_b2.id,
                    "order": AnyStr(),
                    primary_b.db_column: None,
                    link_b_to_a.db_column: [
                        {"id": row_a1.id, "value": "a1", "order": AnyStr()}
                    ],
                },
                {
                    "id": row_b3.id,
                    "order": AnyStr(),
                    primary_b.db_column: None,
                    link_b_to_a.db_column: [
                        {"id": row_a1.id, "value": "a1", "order": AnyStr()}
                    ],
                },
            ],
            "total_count": 3,
        }


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
@override_settings(BATCH_ROWS_SIZE_LIMIT=2)
def test_rows_updated_payload_for_linked_tables_is_paginated(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    primary_a = table_a.get_primary_field()
    primary_b = table_b.get_primary_field()
    link_b_to_a = link_a_to_b.link_row_related_field

    row_b1, row_b2, row_b3 = (
        RowHandler().force_create_rows(user, table_b, [{}, {}, {}]).created_rows
    )

    webhook = data_fixture.create_table_webhook(
        table=table_b,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
        include_all_events=True,
    )

    # Webhook in table b is trigger when creating rows in table a
    # and linking them to rows in table b
    with patch(
        "baserow.contrib.database.webhooks.tasks.make_request_and_save_result",
    ) as p:
        (row_a1,) = (
            RowHandler()
            .force_create_rows(
                user,
                table_a,
                [
                    {
                        primary_a.db_column: "a1",
                        link_a_to_b.db_column: [row_b1.id, row_b2.id, row_b3.id],
                    }
                ],
            )
            .created_rows
        )

        assert p.call_count == 2
        shared_data = {
            "table_id": table_b.id,
            "database_id": table_b.database_id,
            "workspace_id": table_b.database.workspace_id,
            "webhook_id": webhook.id,
            "event_id": AnyStr(),
            "event_type": "rows.updated",
            "total_count": 3,
        }
        first_call_args = p.call_args_list[0][0]
        assert first_call_args[6] == {
            # Send all the rows data
            "items": [
                {
                    "id": row_b1.id,
                    "order": AnyStr(),
                    primary_b.db_column: None,
                    link_b_to_a.db_column: [
                        {"id": row_a1.id, "value": "a1", "order": AnyStr()}
                    ],
                },
                {
                    "id": row_b2.id,
                    "order": AnyStr(),
                    primary_b.db_column: None,
                    link_b_to_a.db_column: [
                        {"id": row_a1.id, "value": "a1", "order": AnyStr()}
                    ],
                },
            ],
            "offset": 0,
            "batch_size": 2,
            "batch_id": 1,
            **shared_data,
        }

        second_call_args = p.call_args_list[1][0]
        assert second_call_args[6] == {
            "items": [
                {
                    "id": row_b3.id,
                    "order": AnyStr(),
                    primary_b.db_column: None,
                    link_b_to_a.db_column: [
                        {"id": row_a1.id, "value": "a1", "order": AnyStr()}
                    ],
                },
            ],
            "offset": 2,
            "batch_size": 1,
            "batch_id": 2,
            **shared_data,
        }


@pytest.mark.django_db(transaction=True)
def test_rows_updated_can_trigger_webhooks_in_linked_tables_without_additional_queries(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)

    row_b1, row_b2, row_b3 = (
        RowHandler().force_create_rows(user, table_b, [{}, {}, {}]).created_rows
    )

    (row_a1,) = RowHandler().force_create_rows(user, table_a, [{}]).created_rows

    def _update_rows():
        RowHandler().force_update_rows(
            user,
            table_a,
            [
                {
                    "id": row_a1.id,
                    link_a_to_b.db_column: [row_b1.id, row_b2.id, row_b3.id],
                }
            ],
        )

    with patch("baserow.contrib.database.webhooks.registries.call_webhook.delay") as p:
        with transaction.atomic(), CaptureQueriesContext(connection) as captured:
            _update_rows()

        assert p.call_count == 0

        # Create a webhook that will be triggered by the update on the related table
        webhook = data_fixture.create_table_webhook(
            table=table_b,
            request_method="POST",
            url="http://localhost",
            use_user_field_names=False,
            include_all_events=True,
        )
        # It's not called without changes to link row values in table_b
        with transaction.atomic(), CaptureQueriesContext(connection) as captured2:
            _update_rows()

        assert p.call_count == 1  # the webhook was called
        assert len(captured.captured_queries) >= len(captured2.captured_queries)
