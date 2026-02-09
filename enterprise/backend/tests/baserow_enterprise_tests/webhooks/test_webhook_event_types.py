from unittest.mock import MagicMock, patch

from django.db import transaction
from django.test.utils import override_settings

import pytest
import responses

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.webhooks.handler import WebhookHandler
from baserow.contrib.database.webhooks.registries import webhook_event_type_registry
from baserow.core.redis import WebhookRedisQueue


@pytest.mark.django_db()
def test_rows_enter_view_event_type(enterprise_data_fixture):
    """
    Test the payload structure for the view.rows_entered webhook event type.
    """

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    view = enterprise_data_fixture.create_grid_view(table=table)
    field = enterprise_data_fixture.create_text_field(
        table=table, primary=True, name="Test 1"
    )

    model = table.get_model()
    row = model.objects.create()
    webhook = enterprise_data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    payload = webhook_event_type_registry.get("view.rows_entered").get_payload(
        event_id="1", webhook=webhook, view=view, row_ids=[row.id]
    )
    serialized_view = {
        "id": view.id,
        "table_id": table.id,
        "order": 0,
        "type": "grid",
        "name": view.name,
        "table": {
            "id": table.id,
            "order": 0,
            "name": table.name,
            "database_id": table.database_id,
        },
        "filters_disabled": False,
        "show_logo": True,
        "allow_public_export": False,
        "public_view_has_password": False,
        "filter_type": "AND",
        "ownership_type": "collaborative",
        "owned_by_id": None,
    }
    expected_payload = {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.rows_entered",
        "total_count": 1,
        "view": serialized_view,
        "row_ids": [row.id],
    }

    assert payload == expected_payload

    paginated_payload, _ = webhook_event_type_registry.get(
        "view.rows_entered"
    ).paginate_payload(webhook, "1", payload)

    assert paginated_payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.rows_entered",
        "total_count": 1,
        "view": serialized_view,
        "fields": ["id", "order", field.db_column],
        "rows": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                field.db_column: None,
            }
        ],
    }

    webhook.use_user_field_names = True
    webhook.save()
    payload = webhook_event_type_registry.get("view.rows_entered").get_payload(
        event_id="1", webhook=webhook, view=view, row_ids=[row.id]
    )
    assert payload == expected_payload

    paginated_payload, _ = webhook_event_type_registry.get(
        "view.rows_entered"
    ).paginate_payload(webhook, "1", payload)

    assert paginated_payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.rows_entered",
        "total_count": 1,
        "view": serialized_view,
        "fields": ["id", "order", "Test 1"],
        "rows": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                "Test 1": None,
            }
        ],
    }


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_enter_view_event_type_require_enterprise_license(
    mock_call_webhook, enterprise_data_fixture, synced_roles
):
    """
    Test that the view.rows_entered event only triggers with an enterprise license.
    """

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    view = enterprise_data_fixture.create_grid_view(table=table)
    with transaction.atomic():
        webhook = WebhookHandler().create_table_webhook(
            user=user,
            table=table,
            url="http://localhost/",
            include_all_events=False,
            events=["view.rows_entered"],
            event_config=[{"event_type": "view.rows_entered", "views": [view.id]}],
            headers={"Baserow-header-1": "Value 1"},
        )

        RowHandler().force_create_rows(user=user, table=table, rows_values=[{}])

    mock_call_webhook.delay.assert_not_called()

    # From now on, the webhook should be called.
    enterprise_data_fixture.enable_enterprise()
    with transaction.atomic():
        RowHandler().force_create_rows(user=user, table=table, rows_values=[{}])

    mock_call_webhook.delay.assert_called_once()
    mock_call_webhook.reset_mock()

    enterprise_data_fixture.delete_all_licenses()
    with transaction.atomic():
        RowHandler().force_create_rows(user=user, table=table, rows_values=[{}])

    mock_call_webhook.delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_enter_view_event_type_not_triggerd_with_include_all_events(
    mock_call_webhook, enterprise_data_fixture, enable_enterprise, synced_roles
):
    """Test that view.rows_entered is not triggered when include_all_events is True."""

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    view = enterprise_data_fixture.create_grid_view(table=table)

    with transaction.atomic():
        webhook = WebhookHandler().create_table_webhook(
            user=user, table=table, url="http://localhost/", include_all_events=True
        )

        RowHandler().force_create_rows(user=user, table=table, rows_values=[{}])

    assert mock_call_webhook.delay.call_count == 1
    assert mock_call_webhook.delay.call_args[1]["event_type"] == "rows.created"


@pytest.mark.django_db()
def test_rows_enter_view_event_event_type_test_payload(enterprise_data_fixture):
    """Test the test/mock payload generation for the view.rows_entered event type."""

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    field = enterprise_data_fixture.create_text_field(
        table=table, primary=True, name="Test 1"
    )

    model = table.get_model()
    webhook = enterprise_data_fixture.create_table_webhook(
        table=table,
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    webhook_event_type = webhook_event_type_registry.get("view.rows_entered")
    payload = webhook_event_type.get_test_call_payload(table, model, "1", webhook)
    serialized_view = {
        "id": 0,
        "table_id": table.id,
        "order": 1,
        "type": "grid",
        "name": "View",
        "table": {
            "id": table.id,
            "order": 0,
            "name": table.name,
            "database_id": table.database_id,
        },
        "filters_disabled": False,
        "show_logo": True,
        "allow_public_export": False,
        "public_view_has_password": False,
        "filter_type": "AND",
        "ownership_type": "collaborative",
        "owned_by_id": None,
    }
    assert payload == {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_id": "1",
        "event_type": "view.rows_entered",
        "total_count": 1,
        "view": serialized_view,
        "row_ids": [0],
    }


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_enter_view_event_type_not_called_without_view(
    mock_call_webhook, enterprise_data_fixture, enable_enterprise, synced_roles
):
    """Test that the webhook is not called when no views are configured."""

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    view = enterprise_data_fixture.create_grid_view(table=table)

    with transaction.atomic():  # No views
        webhook = WebhookHandler().create_table_webhook(
            user=user,
            table=table,
            url="http://localhost/",
            include_all_events=False,
            events=["view.rows_entered"],
            event_config=[{"event_type": "view.rows_entered", "views": []}],
            headers={"Baserow-header-1": "Value 1"},
        )

        RowHandler().force_create_rows(user=user, table=table, rows_values=[{}])

    mock_call_webhook.delay.assert_not_called()

    with transaction.atomic():  # Now with a view
        WebhookHandler().update_table_webhook(
            user=user,
            webhook=webhook,
            events=["view.rows_entered"],
            event_config=[{"event_type": "view.rows_entered", "views": [view.id]}],
            headers={"Baserow-header-1": "Value 1"},
        )

        RowHandler().force_create_rows(user=user, table=table, rows_values=[{}])

    mock_call_webhook.delay.assert_called_once()


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_enter_view_event_type_called_once_per_view(
    mock_call_webhook, enterprise_data_fixture, enable_enterprise, synced_roles
):
    """Test that the webhook is called once for each configured view."""

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    view_a = enterprise_data_fixture.create_grid_view(table=table)
    view_b = enterprise_data_fixture.create_grid_view(table=table)

    with transaction.atomic():
        WebhookHandler().create_table_webhook(
            user=user,
            table=table,
            url="http://localhost/",
            include_all_events=False,
            events=["view.rows_entered"],
            event_config=[
                {"event_type": "view.rows_entered", "views": [view_a.id, view_b.id]}
            ],
            headers={"Baserow-header-1": "Value 1"},
        )

        RowHandler().force_create_rows(user=user, table=table, rows_values=[{}])

    assert mock_call_webhook.delay.call_count == 2


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_enter_view_event_type_only_right_webhook_is_called(
    mock_call_webhook, enterprise_data_fixture, enable_enterprise, synced_roles
):
    """Test that only the webhook for the correct table/view is triggered."""

    user = enterprise_data_fixture.create_user()
    table_a = enterprise_data_fixture.create_database_table(user=user)
    view_a = enterprise_data_fixture.create_grid_view(table=table_a)

    table_b = enterprise_data_fixture.create_database_table(user=user)
    view_b = enterprise_data_fixture.create_grid_view(table=table_b)

    with transaction.atomic():
        WebhookHandler().create_table_webhook(
            user=user,
            table=table_a,
            url="http://localhost/",
            include_all_events=False,
            events=["view.rows_entered"],
            event_config=[{"event_type": "view.rows_entered", "views": [view_a.id]}],
            headers={"Baserow-header-1": "Value 1"},
        )
        WebhookHandler().create_table_webhook(
            user=user,
            table=table_b,
            url="http://localhost/",
            include_all_events=False,
            events=["view.rows_entered"],
            event_config=[{"event_type": "view.rows_entered", "views": [view_b.id]}],
            headers={"Baserow-header-1": "Value 1"},
        )

        RowHandler().force_create_rows(user=user, table=table_a, rows_values=[{}])

    assert mock_call_webhook.delay.call_count == 1


@pytest.mark.django_db(transaction=True)
@responses.activate
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
@patch(
    "baserow.contrib.database.webhooks.tasks.make_request_and_save_result",
    side_effect=lambda *args, **kwargs: True,
)
@override_settings(DEBUG=True, BASEROW_WEBHOOK_ROWS_ENTER_VIEW_BATCH_SIZE=2)
def test_rows_enter_view_event_type_paginate_data(
    mock_make_request, enterprise_data_fixture, enable_enterprise, synced_roles
):
    """Test that large row batches are paginated into multiple webhook calls."""

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="text")
    view = enterprise_data_fixture.create_grid_view(table=table)

    responses.add(responses.POST, "http://localhost/", json={}, status=200)

    webhook = WebhookHandler().create_table_webhook(
        user=user,
        table=table,
        url="http://localhost/",
        include_all_events=True,
    )

    serialized_view = {
        "id": view.id,
        "table_id": table.id,
        "order": 0,
        "type": "grid",
        "name": view.name,
        "table": {
            "id": table.id,
            "order": 0,
            "name": table.name,
            "database_id": table.database_id,
        },
        "filters_disabled": False,
        "show_logo": True,
        "allow_public_export": False,
        "public_view_has_password": False,
        "filter_type": "AND",
        "ownership_type": "collaborative",
        "owned_by_id": None,
    }
    expected_first_page_payload = {
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_type": "view.rows_entered",
        "offset": 0,
        "total_count": 3,
        "batch_id": 1,
        "batch_size": 2,
        "view": serialized_view,
        "fields": ["id", "order", "text"],
        "rows": [
            {"id": 1, "order": "1.00000000000000000000", "text": "a"},
            {"id": 2, "order": "2.00000000000000000000", "text": "b"},
        ],
    }

    with transaction.atomic():
        WebhookHandler().update_table_webhook(
            user=user,
            webhook=webhook,
            include_all_events=False,
            events=["view.rows_entered"],
            event_config=[{"event_type": "view.rows_entered", "views": [view.id]}],
            headers={"Baserow-header-1": "Value 1"},
            use_user_field_names=True,
        )

        RowHandler().force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {text_field.db_column: "a"},
                {text_field.db_column: "b"},
                {text_field.db_column: "c"},
            ],
        )

    assert mock_make_request.call_count == 2
    first_call_args = mock_make_request.call_args_list[0][0]
    event_id = first_call_args[1]
    first_page_payload = first_call_args[6]

    # first batch
    expected_first_page_payload["event_id"] = event_id
    assert first_page_payload == expected_first_page_payload

    # second batch
    second_call_args = mock_make_request.call_args_list[1][0]
    second_page_payload = second_call_args[6]
    assert second_page_payload == {
        "event_id": event_id,
        "table_id": table.id,
        "database_id": table.database_id,
        "workspace_id": table.database.workspace_id,
        "webhook_id": webhook.id,
        "event_type": "view.rows_entered",
        "offset": 2,
        "total_count": 3,
        "batch_id": 2,
        "batch_size": 1,
        "view": serialized_view,
        "fields": ["id", "order", "text"],
        "rows": [
            {"id": 3, "order": "3.00000000000000000000", "text": "c"},
        ],
    }


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@responses.activate
@patch("baserow.contrib.database.webhooks.registries.call_webhook")
def test_rows_enter_view_webhook_does_not_trigger_for_events_before_creation(
    mock_call_webhook, enterprise_data_fixture, synced_roles, enable_enterprise
):
    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Fruit")

    banana_view = enterprise_data_fixture.create_grid_view(table=table)
    enterprise_data_fixture.create_view_filter(
        view=banana_view, field=text_field, type="equal", value="Banana"
    )

    # Create some rows
    rows = (
        RowHandler()
        .force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {f"field_{text_field.id}": "Apple"},
                {f"field_{text_field.id}": "Banana"},  # in banana_view
                {f"field_{text_field.id}": "Carrot"},
                {f"field_{text_field.id}": "Banana"},
                {f"field_{text_field.id}": "Mango"},
            ],
        )
        .created_rows
    )

    with transaction.atomic():
        webhook_1 = WebhookHandler().create_table_webhook(
            user=user,
            table=table,
            url="http://localhost/webhook_1",
            include_all_events=False,
            events=["view.rows_entered"],
            event_config=[
                {"event_type": "view.rows_entered", "views": [banana_view.id]}
            ],
        )

    # The webhook should not trigger the first time
    assert mock_call_webhook.delay.call_count == 0

    # Now let's remove the webhook, update some rows and re-create the webhook.
    # Also the new one, should not trigger the first time
    WebhookHandler().delete_table_webhook(user, webhook_1)

    with transaction.atomic():
        RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[
                {"id": rows[0].id, f"field_{text_field.id}": "Banana"},
                {"id": rows[3].id, f"field_{text_field.id}": "Banana no more"},
            ],
        )
    with transaction.atomic():
        webhook_2 = WebhookHandler().create_table_webhook(
            user=user,
            table=table,
            url="http://localhost/webhook_2",
            include_all_events=False,
            events=["view.rows_entered"],
            event_config=[
                {"event_type": "view.rows_entered", "views": [banana_view.id]}
            ],
        )

    assert mock_call_webhook.delay.call_count == 0

    with transaction.atomic():
        RowHandler().force_update_rows(
            user=user,
            table=table,
            rows_values=[
                {"id": rows[2].id, f"field_{text_field.id}": "Banana"},
            ],
        )

    assert mock_call_webhook.delay.call_count == 1
    assert mock_call_webhook.delay.call_args[1]["event_type"] == "view.rows_entered"
    # Only row[2] entered the view since we recreated the webhook
    assert mock_call_webhook.delay.call_args[1]["payload"]["row_ids"] == [rows[2].id]
