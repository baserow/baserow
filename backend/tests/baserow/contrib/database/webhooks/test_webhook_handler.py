import json

from django.core.exceptions import ValidationError
from django.test import override_settings

import pytest
import responses

from baserow.contrib.database.webhooks.exceptions import (
    TableWebhookDoesNotExist,
    TableWebhookMaxAllowedCountExceeded,
)
from baserow.contrib.database.webhooks.handler import WebhookHandler
from baserow.contrib.database.webhooks.models import TableWebhook, TableWebhookCall
from baserow.contrib.database.webhooks.registries import webhook_event_type_registry
from baserow.core.exceptions import UserNotInWorkspace


@pytest.mark.django_db
def test_find_webhooks_to_call(data_fixture):
    table_1 = data_fixture.create_database_table()
    table_2 = data_fixture.create_database_table()
    webhook_1 = data_fixture.create_table_webhook(
        table=table_1, include_all_events=True, active=True
    )
    webhook_2 = data_fixture.create_table_webhook(
        table=table_1, include_all_events=False, events=["rows.created"], active=True
    )
    data_fixture.create_table_webhook(
        table=table_1, include_all_events=False, events=["rows.updated"], active=False
    )
    webhook_4 = data_fixture.create_table_webhook(
        table=table_1,
        include_all_events=False,
        events=["rows.updated", "rows.deleted"],
        active=True,
    )
    webhook_5 = data_fixture.create_table_webhook(
        table=table_2,
        include_all_events=True,
        active=True,
    )
    webhook_6 = data_fixture.create_table_webhook(
        table=table_2,
        include_all_events=False,
        events=["rows.updated"],
        active=True,
    )

    handler = WebhookHandler()

    webhooks = handler.find_webhooks_to_call(
        webhook_event_type_registry.get("rows.created"),
        table=table_1,
        model=table_1.get_model(),
    )
    webhook_ids = [webhook.id for webhook in webhooks]
    assert len(webhook_ids) == 2
    assert webhook_1.id in webhook_ids
    assert webhook_2.id in webhook_ids

    webhooks = handler.find_webhooks_to_call(
        webhook_event_type_registry.get("rows.updated"),
        table=table_1,
        model=table_1.get_model(),
    )
    webhook_ids = [webhook.id for webhook in webhooks]
    assert len(webhook_ids) == 2
    assert webhook_1.id in webhook_ids
    assert webhook_4.id in webhook_ids

    webhooks = handler.find_webhooks_to_call(
        webhook_event_type_registry.get("rows.deleted"),
        table=table_1,
        model=table_1.get_model(),
    )
    webhook_ids = [webhook.id for webhook in webhooks]
    assert len(webhook_ids) == 2
    assert webhook_1.id in webhook_ids
    assert webhook_4.id in webhook_ids

    webhooks = handler.find_webhooks_to_call(
        webhook_event_type_registry.get("rows.created"),
        table=table_2,
        model=table_2.get_model(),
    )
    webhook_ids = [webhook.id for webhook in webhooks]
    assert len(webhook_ids) == 1
    assert webhook_5.id in webhook_ids

    webhooks = handler.find_webhooks_to_call(
        webhook_event_type_registry.get("rows.updated"),
        table=table_2,
        model=table_2.get_model(),
    )
    webhook_ids = [webhook.id for webhook in webhooks]
    assert len(webhook_ids) == 2
    assert webhook_5.id in webhook_ids
    assert webhook_6.id in webhook_ids

    webhooks = handler.find_webhooks_to_call(
        webhook_event_type_registry.get("rows.deleted"),
        table=table_2,
        model=table_2.get_model(),
    )
    webhook_ids = [webhook.id for webhook in webhooks]
    assert len(webhook_ids) == 1
    assert webhook_5.id in webhook_ids


@pytest.mark.django_db()
def test_get_webhook(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    webhook_handler = WebhookHandler()

    webhook = data_fixture.create_table_webhook(table=table, user=user)
    gotten_webhook = webhook_handler.get_table_webhook(user, webhook.id)
    assert gotten_webhook.id == webhook.id

    # trying to get unknown webhook will result in exception
    with pytest.raises(TableWebhookDoesNotExist):
        webhook_handler.get_table_webhook(user, 0)

    # user with no permission to the table will not be able to access webhook
    user_2 = data_fixture.create_user()
    with pytest.raises(UserNotInWorkspace):
        webhook_handler.get_table_webhook(user_2, webhook.id)

    with pytest.raises(AttributeError):
        webhook_handler.get_table_webhook(
            user,
            webhook.id,
            base_queryset=TableWebhook.objects.prefetch_related("UNKNOWN"),
        )


@pytest.mark.django_db()
def test_get_all_table_webhooks(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    webhook_1 = data_fixture.create_table_webhook(
        table=table,
        events=["rows.created", "rows.updated"],
        headers={"Baserow-test-2": "Value 2"},
        include_all_events=False,
    )
    webhook_2 = data_fixture.create_table_webhook(
        table=table, headers={"Baserow-test-1": "Value 1"}, include_all_events=True
    )
    data_fixture.create_table_webhook()

    handler = WebhookHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.get_all_table_webhooks(user_2, table)

    webhooks = handler.get_all_table_webhooks(user, table)

    assert len(webhooks) == 2
    assert webhooks[0].id == webhook_1.id
    assert webhooks[1].id == webhook_2.id

    with django_assert_num_queries(0):
        list(webhooks[0].events.all())
        list(webhooks[0].headers.all())
        list(webhooks[1].events.all())
        list(webhooks[1].headers.all())


@pytest.mark.django_db(transaction=True)
@override_settings(BASEROW_WEBHOOKS_MAX_PER_TABLE=4)
def test_create_webhook(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    webhook_handler = WebhookHandler()

    webhook_data = {
        "url": "https://baserow.io/endpoint",
        "name": "My Webhook",
        "include_all_events": True,
        "request_method": "POST",
    }

    with pytest.raises(UserNotInWorkspace):
        webhook_handler.create_table_webhook(user=user_2, table=table, **webhook_data)

    webhook = webhook_handler.create_table_webhook(
        user=user, table=table, **webhook_data
    )

    assert webhook.name == webhook_data["name"]
    assert webhook.url == webhook_data["url"]
    assert webhook.include_all_events == webhook_data["include_all_events"]
    assert webhook.table_id == table.id
    assert webhook.request_method == "POST"
    events = webhook.events.all()
    assert len(events) == 0
    headers = webhook.headers.all()
    assert len(headers) == 0

    # new url
    webhook_data["url"] = "https://baserow.io/endpoint-2"

    # if "include_all_events" is True and we pass in events that are not empty
    # the handler will not create the entry in the events table.
    events = ["rows.created"]
    webhook = webhook_handler.create_table_webhook(
        user=user, table=table, events=events, headers={}, **webhook_data
    )
    webhook_events = webhook.events.all()
    assert len(webhook_events) == 0

    # when we set "include_all_events" to False then we expect that the events will be
    # added
    webhook_data["include_all_events"] = False
    webhook_data["url"] = "https://baserow.io/endpoint-3"
    headers = {"Baserow-test-1": "Value 1", "Baserow-header-2": "Value 2"}
    webhook = webhook_handler.create_table_webhook(
        user=user, table=table, events=events, headers=headers, **webhook_data
    )
    assert webhook.include_all_events is False
    webhook_events = webhook.events.all()
    assert len(webhook_events) == 1
    assert webhook_events[0].event_type == "rows.created"
    webhook_headers = webhook.headers.all()
    assert len(webhook_headers) == 2
    assert webhook_headers[0].name == "Baserow-test-1"
    assert webhook_headers[0].value == "Value 1"
    assert webhook_headers[1].name == "Baserow-header-2"
    assert webhook_headers[1].value == "Value 2"

    # By providing an invalid header name, we expect it to fail.
    with pytest.raises(ValidationError):
        webhook_handler.create_table_webhook(
            user=user, table=table, headers={"Test:": ""}, **webhook_data
        )

    # check that we can't create more than "MAX_ALLOWED_WEBHOOKS" per table
    webhook_data["include_all_events"] = True
    webhook_data["url"] = "https://baserow.io/endpoint-4"
    with pytest.raises(TableWebhookMaxAllowedCountExceeded):
        webhook_handler.create_table_webhook(
            user=user, table=table, events=events, headers={}, **webhook_data
        )


@pytest.mark.django_db(transaction=True)
def test_update_webhook(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    webhook = data_fixture.create_table_webhook(
        table=table,
        events=["rows.created"],
        headers={"Baserow-test-1": "Value 1", "Baserow-test-2": "Value 2"},
    )

    handler = WebhookHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.update_table_webhook(user=user_2, webhook=webhook, name="Test")

    webhook = handler.update_table_webhook(
        user=user,
        webhook=webhook,
        name="Test",
        url="https://baserow.io/endpoint",
        include_all_events=False,
        request_method="GET",
        use_user_field_names=False,
        active=False,
    )
    assert webhook.name == "Test"
    assert webhook.url == "https://baserow.io/endpoint"
    assert webhook.include_all_events is False
    assert webhook.request_method == "GET"
    assert webhook.use_user_field_names is False
    assert webhook.active is False
    assert webhook.events.all().count() == 1
    assert webhook.headers.all().count() == 2

    events_before = list(webhook.events.all())
    webhook = handler.update_table_webhook(
        user=user, webhook=webhook, events=["rows.created", "rows.updated"]
    )
    events = webhook.events.all().order_by("id")
    assert len(events) == 2
    assert events[0].id == events_before[0].id
    assert events[0].event_type == events_before[0].event_type == "rows.created"
    assert events[1].event_type == "rows.updated"

    webhook = handler.update_table_webhook(
        user=user, webhook=webhook, events=["rows.updated"]
    )
    events_2 = webhook.events.all().order_by("id")
    assert len(events_2) == 1
    assert events_2[0].id == events[1].id
    assert events_2[0].event_type == events[1].event_type == "rows.updated"

    webhook = handler.update_table_webhook(
        user=user, webhook=webhook, include_all_events=True, events=["rows.created"]
    )
    assert webhook.events.all().count() == 0

    old_headers = list(webhook.headers.all())
    webhook = handler.update_table_webhook(
        user=user,
        webhook=webhook,
        headers={"Baserow-test-1": "Updated 1", "Baserow-test-3": "Updated 3"},
    )
    headers = webhook.headers.all()
    assert len(headers) == 2
    assert headers[0].id == old_headers[0].id
    assert headers[0].name == "Baserow-test-1"
    assert headers[0].value == "Updated 1"
    assert headers[1].name == "Baserow-test-3"
    assert headers[1].value == "Updated 3"


@pytest.mark.django_db()
def test_delete_webhook(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    webhook = data_fixture.create_table_webhook(
        user=user,
        headers={"A": "B"},
        events=["rows.created"],
        include_all_events=False,
    )
    data_fixture.create_table_webhook()

    handler = WebhookHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.delete_table_webhook(user=user_2, webhook=webhook)

    handler.delete_table_webhook(user=user, webhook=webhook)
    assert TableWebhook.objects.all().count() == 1


@pytest.mark.django_db
@responses.activate
def test_trigger_test_call(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, primary=True, name="Test 1")

    handler = WebhookHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.trigger_test_call(user=user_2, table=table, event_type="rows.created")

    responses.add(responses.POST, "http://localhost", json={}, status=200)

    request, response = handler.trigger_test_call(
        user=user,
        table=table,
        event_type="rows.created",
        headers={"Baserow-add-1": "Value 1"},
        request_method="POST",
        url="http://localhost",
        use_user_field_names=False,
    )
    assert response.ok

    assert response.request.headers["Baserow-add-1"] == "Value 1"
    assert response.request.headers["Content-type"] == "application/json"
    assert response.request.headers["X-Baserow-Event"] == "rows.created"
    assert "X-Baserow-Delivery" in request.headers

    assert request.method == "POST"
    assert request.url == "http://localhost/"

    request_body = json.loads(request.body)
    assert request_body["table_id"] == table.id
    assert request_body["event_type"] == "rows.created"
    assert request_body["items"] == [
        {
            "id": 0,
            f"field_{field.id}": None,
            "order": "0.00000000000000000000",
        }
    ]


@pytest.mark.django_db
@override_settings(BASEROW_WEBHOOKS_MAX_CALL_LOG_ENTRIES=2)
def test_clean_webhook_calls(data_fixture):
    webhook = data_fixture.create_table_webhook()
    deleted_1 = data_fixture.create_table_webhook_call(webhook=webhook)  # deleted
    deleted_2 = data_fixture.create_table_webhook_call(webhook=webhook)  # deleted
    data_fixture.create_table_webhook_call(webhook=webhook)
    data_fixture.create_table_webhook_call(webhook=webhook)

    webhook_2 = data_fixture.create_table_webhook()
    deleted_3 = data_fixture.create_table_webhook_call(webhook=webhook_2)
    data_fixture.create_table_webhook_call(webhook=webhook_2)
    data_fixture.create_table_webhook_call(webhook=webhook_2)

    handler = WebhookHandler()
    handler.clean_webhook_calls(webhook=webhook)
    handler.clean_webhook_calls(webhook=webhook_2)

    assert TableWebhookCall.objects.all().count() == 4
    assert (
        TableWebhookCall.objects.filter(
            id__in=[deleted_1.id, deleted_2.id, deleted_3.id]
        ).count()
        == 0
    )
