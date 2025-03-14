from unittest.mock import MagicMock, patch

from django.db import transaction
from django.test import override_settings

import httpretty
import pytest
import responses
from celery.exceptions import Retry

from baserow.contrib.database.webhooks.models import TableWebhook, TableWebhookCall
from baserow.contrib.database.webhooks.notification_types import (
    WebhookDeactivatedNotificationType,
    WebhookPayloadTooLargeNotificationType,
)
from baserow.contrib.database.webhooks.registries import WebhookEventType
from baserow.contrib.database.webhooks.tasks import (
    call_webhook,
    enqueue_webhook_task,
    schedule_next_task_in_queue,
)
from baserow.core.models import WorkspaceUser
from baserow.core.notifications.models import Notification
from baserow.core.redis import WebhookRedisQueue
from baserow.test_utils.helpers import stub_getaddrinfo


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=1,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=1,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
@patch("baserow.contrib.database.webhooks.tasks.clear_webhook_queue")
def test_call_webhook_webhook_does_not_exist(mock_clear_queue):
    # webhook_id=0 does not exist, and will therefore be skipped.
    call_webhook.run(
        webhook_id=0,
        event_id="00000000-0000-0000-0000-000000000000",
        event_type="rows.created",
        method="POST",
        url="http://localhost/",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )
    assert TableWebhookCall.objects.all().count() == 0
    mock_clear_queue.assert_called_with(0)


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=1,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=1,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_call_webhook_webhook_url_cannot_be_reached(data_fixture):
    webhook = data_fixture.create_table_webhook()

    # failed because http://localhost/ can't be reached.
    with pytest.raises(Retry):
        call_webhook.run(
            webhook_id=webhook.id,
            event_id="00000000-0000-0000-0000-000000000000",
            event_type="rows.created",
            method="POST",
            url="http://localhost/",
            headers={"Baserow-header-1": "Value 1"},
            payload={"type": "rows.created"},
        )
        transaction.commit()

    assert TableWebhookCall.objects.all().count() == 1
    created_call = TableWebhookCall.objects.all().first()
    assert created_call.webhook_id == webhook.id
    assert created_call.event_type == "rows.created"
    assert created_call.called_time
    assert created_call.called_url == "http://localhost/"
    assert "POST http://localhost/" in created_call.request
    assert created_call.response is None
    assert created_call.response_status is None
    assert "Connection refused by Responses" in created_call.error

    webhook.refresh_from_db()
    assert webhook.active is True
    assert webhook.failed_triggers == 1


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=1,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=1,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_call_webhook_becomes_inactive_max_failed_reached(data_fixture):
    webhook = data_fixture.create_table_webhook(active=True, failed_triggers=1)

    call_webhook.push_request(retries=1)
    call_webhook.run(
        webhook_id=webhook.id,
        event_id="00000000-0000-0000-0000-000000000000",
        event_type="rows.created",
        method="POST",
        url="http://localhost/",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )

    webhook.refresh_from_db()
    assert webhook.active is False
    assert webhook.failed_triggers == 1
    assert TableWebhookCall.objects.all().count() == 1


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=1,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=1,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_call_webhook_skipped_because_not_active(data_fixture):
    webhook = data_fixture.create_table_webhook(active=False, failed_triggers=1)

    call_webhook.run(
        webhook_id=webhook.id,
        event_id="00000000-0000-0000-0000-000000000000",
        event_type="rows.created",
        method="POST",
        url="http://localhost/",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )

    webhook.refresh_from_db()
    assert webhook.active is False
    assert webhook.failed_triggers == 1
    assert TableWebhookCall.objects.all().count() == 0


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=1,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=1,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_call_webhook_reset_after_success_call(data_fixture):
    webhook = data_fixture.create_table_webhook(failed_triggers=1)
    responses.add(responses.POST, "http://localhost/", json={}, status=200)

    call_webhook.push_request(retries=0)
    call_webhook(
        webhook_id=webhook.id,
        event_id="00000000-0000-0000-0000-000000000002",
        event_type="rows.created",
        method="POST",
        url="http://localhost/",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )

    webhook.refresh_from_db()
    assert webhook.active is True
    assert webhook.failed_triggers == 0


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=1,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=1,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_call_webhook(data_fixture):
    webhook = data_fixture.create_table_webhook()
    responses.add(responses.POST, "http://localhost/", json={}, status=200)

    call_webhook.push_request(retries=0)
    call_webhook(
        webhook_id=webhook.id,
        event_id="00000000-0000-0000-0000-000000000002",
        event_type="rows.created",
        method="POST",
        url="http://localhost/",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )

    assert TableWebhookCall.objects.all().count() == 1
    created_call = TableWebhookCall.objects.all().first()
    assert created_call.webhook_id == webhook.id
    assert created_call.event_type == "rows.created"
    assert created_call.called_time
    assert created_call.called_url == "http://localhost/"
    assert "POST http://localhost/" in created_call.request
    assert "{}" in created_call.response
    assert created_call.response_status == 200
    assert created_call.error == ""

    webhook.refresh_from_db()
    assert webhook.active is True
    assert webhook.failed_triggers == 0

    responses.add(responses.POST, "http://localhost2/", json={}, status=400)
    call_webhook.push_request(retries=0)

    with pytest.raises(Retry):
        call_webhook(
            webhook_id=webhook.id,
            event_id="00000000-0000-0000-0000-000000000003",
            event_type="rows.created",
            method="POST",
            url="http://localhost2/",
            headers={"Baserow-header-1": "Value 1"},
            payload={"type": "rows.created"},
        )

    assert TableWebhookCall.objects.all().count() == 2
    created_call = TableWebhookCall.objects.all().first()
    assert created_call.webhook_id == webhook.id
    assert created_call.event_type == "rows.created"
    assert created_call.called_time
    assert created_call.called_url == "http://localhost2/"
    assert "POST http://localhost2/" in created_call.request
    assert "{}" in created_call.response
    assert created_call.response_status == 400
    assert created_call.error == ""


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
@responses.activate
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_call_webhook_concurrent_task_moved_to_queue(data_fixture):
    from baserow.contrib.database.webhooks.tasks import get_queue

    webhook = data_fixture.create_table_webhook()
    responses.add(responses.POST, "http://localhost/", json={}, status=200)

    with transaction.atomic(using="default-copy"):
        TableWebhook.objects.using("default-copy").select_for_update().get(
            id=webhook.id
        )

        call_webhook(
            webhook_id=webhook.id,
            event_id="00000000-0000-0000-0000-000000000002",
            event_type="rows.created",
            method="POST",
            url="http://localhost/",
            headers={"Baserow-header-1": "Value 1"},
            payload={"type": "rows.created"},
        )

        queue = get_queue(webhook.id)
        assert len(queue.queues[f"webhook_{webhook.id}_queue"]) == 1


@pytest.mark.django_db(transaction=True, databases=["default"])
@responses.activate
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
@patch("baserow.contrib.database.webhooks.tasks.schedule_next_task_in_queue")
def test_call_webhook_next_item_scheduled(mock_schedule, data_fixture):
    webhook = data_fixture.create_table_webhook()
    responses.add(responses.POST, "http://localhost/", json={}, status=200)

    call_webhook(
        webhook_id=webhook.id,
        event_id="00000000-0000-0000-0000-000000000002",
        event_type="rows.created",
        method="POST",
        url="http://localhost/",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )

    mock_schedule.assert_called_with(webhook.id)


@pytest.mark.django_db(transaction=True)
@override_settings(
    BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS=False,
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=0,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=0,
)
@httpretty.activate(verbose=True, allow_net_connect=False)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_cant_call_webhook_to_localhost_when_private_addresses_not_allowed(
    patched_getaddrinfo,
    data_fixture,
):
    httpretty.register_uri(httpretty.POST, "http://127.0.0.1", status=200)
    webhook = data_fixture.create_table_webhook()

    assert webhook.active
    call_webhook.run(
        webhook_id=webhook.id,
        event_id="00000000-0000-0000-0000-000000000000",
        event_type="rows.created",
        method="POST",
        url="http://127.0.0.1",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )
    call = TableWebhookCall.objects.get(webhook=webhook)
    webhook.refresh_from_db()
    assert call.error == "UnacceptableAddressException: ('127.0.0.1', 80)"
    assert not webhook.active


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_ALLOW_PRIVATE_ADDRESS=True,
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=0,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=0,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_can_call_webhook_to_localhost_when_private_addresses_allowed(
    data_fixture,
):
    responses.add(
        responses.POST,
        "http://127.0.0.1",
        status=201,
    )
    webhook = data_fixture.create_table_webhook()

    assert webhook.active
    call_webhook.run(
        webhook_id=webhook.id,
        event_id="00000000-0000-0000-0000-000000000000",
        event_type="rows.created",
        method="POST",
        url="http://127.0.0.1",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )
    call = TableWebhookCall.objects.get(webhook=webhook)
    webhook.refresh_from_db()
    assert not call.error
    assert call.response_status == 201
    assert webhook.active


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=1,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=1,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_call_webhook_failed_reached_notification_send(
    mocked_broadcast_to_users, data_fixture
):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    admin_1 = data_fixture.create_user()
    admin_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    WorkspaceUser.objects.create(
        user=user_1, workspace=workspace, order=1, permissions="MEMBER"
    )
    WorkspaceUser.objects.create(
        user=user_2, workspace=workspace, order=2, permissions="MEMBER"
    )
    WorkspaceUser.objects.create(
        user=admin_1, workspace=workspace, order=3, permissions="ADMIN"
    )
    WorkspaceUser.objects.create(
        user=admin_2, workspace=workspace, order=4, permissions="ADMIN"
    )

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    webhook = data_fixture.create_table_webhook(
        table=table, active=True, failed_triggers=1
    )

    call_webhook.push_request(retries=1)
    call_webhook.run(
        webhook_id=webhook.id,
        event_id="00000000-0000-0000-0000-000000000000",
        event_type="rows.created",
        method="POST",
        url="http://localhost/",
        headers={"Baserow-header-1": "Value 1"},
        payload={"type": "rows.created"},
    )

    all_notifications = list(Notification.objects.all())
    assert len(all_notifications) == 1
    recipient_ids = [r.id for r in all_notifications[0].recipients.all()]
    assert recipient_ids == [admin_1.id, admin_2.id]
    assert all_notifications[0].type == WebhookDeactivatedNotificationType.type
    assert all_notifications[0].broadcast is False
    assert all_notifications[0].workspace_id == workspace.id
    assert all_notifications[0].sender is None
    assert all_notifications[0].data == {
        "database_id": database.id,
        "table_id": table.id,
        "webhook_id": webhook.id,
        "webhook_name": webhook.name,
    }

    # the webhook should be deactivated after the notification is sent.
    webhook.refresh_from_db()
    assert webhook.active is False


class PaginatedWebhookEventType(WebhookEventType):
    type = "test.paginated"

    def __init__(self):
        self.i = 1

    def _paginate_payload(self, webhook, event_id, payload) -> tuple[dict, dict | None]:
        payload["data"] = f"part {self.i}"
        self.i += 1
        return payload, {"data": f"part {self.i}"}


@pytest.mark.django_db(transaction=True)
@responses.activate
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
def test_webhook_with_paginated_payload(
    mutable_webhook_event_type_registry, data_fixture
):
    mutable_webhook_event_type_registry.register(PaginatedWebhookEventType())

    webhook = data_fixture.create_table_webhook()
    responses.add(responses.POST, "http://localhost/", json={}, status=200)
    event_id = "00000000-0000-0000-0000-000000000002"
    expected_payload = (
        webhook.id,
        event_id,
        "test.paginated",
        "POST",
        "http://localhost/",
        {},
        {"batch_id": 2, "data": "part 2"},
    )

    # The first page of the payload is sent and contains the batch_id 1.
    with patch(
        "baserow.contrib.database.webhooks.tasks.enqueue_webhook_task"
    ) as mock_enqueue, patch(
        "baserow.contrib.database.webhooks.tasks.schedule_next_task_in_queue"
    ) as mock_schedule:
        call_webhook(
            webhook_id=webhook.id,
            event_id=event_id,
            event_type="test.paginated",
            method="POST",
            url="http://localhost/",
            headers={},
            payload={},
        )

        assert mock_enqueue.call_args[0][2] == expected_payload
        mock_schedule.assert_called_with(webhook.id)

    assert TableWebhookCall.objects.all().count() == 1
    assert TableWebhookCall.objects.filter(event_id=event_id).first().batch_id == 1

    # we mocked this function to ensure the enqueued payload is correct, now if we call
    # the function again, we should see the next batch_id being sent.
    enqueue_webhook_task(webhook.id, event_id, expected_payload, {})

    with patch(
        "baserow.contrib.database.webhooks.tasks.enqueue_webhook_task"
    ) as mock_enqueue:
        schedule_next_task_in_queue(webhook.id)
        assert mock_enqueue.call_args[0][2] == (
            webhook.id,
            event_id,
            "test.paginated",
            "POST",
            "http://localhost/",
            {},
            {"batch_id": 3, "data": "part 3"},
        )
    assert TableWebhookCall.objects.all().count() == 2
    # Same event_id, but different batch_id.
    assert TableWebhookCall.objects.filter(event_id=event_id).first().batch_id == 2


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(BASEROW_WEBHOOKS_BATCH_LIMIT=1)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", WebhookRedisQueue)
@patch("baserow.contrib.database.webhooks.tasks.cache", MagicMock())
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_call_webhook_payload_too_large_send_notification(
    mocked_broadcast_to_users, mutable_webhook_event_type_registry, data_fixture
):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    admin_1 = data_fixture.create_user()
    admin_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    WorkspaceUser.objects.create(
        user=user_1, workspace=workspace, order=1, permissions="MEMBER"
    )
    WorkspaceUser.objects.create(
        user=user_2, workspace=workspace, order=2, permissions="MEMBER"
    )
    WorkspaceUser.objects.create(
        user=admin_1, workspace=workspace, order=3, permissions="ADMIN"
    )
    WorkspaceUser.objects.create(
        user=admin_2, workspace=workspace, order=4, permissions="ADMIN"
    )

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    mutable_webhook_event_type_registry.register(PaginatedWebhookEventType())
    webhook = data_fixture.create_table_webhook(table=table, active=True)
    responses.add(responses.POST, "http://localhost/", json={}, status=200)
    event_id = "00000000-0000-0000-0000-000000000002"
    expected_payload = (
        webhook.id,
        event_id,
        "test.paginated",
        "POST",
        "http://localhost/",
        {},
        {"batch_id": 2, "data": "part 2"},
    )

    # The first page of the payload is sent and contains the batch_id 1.
    with patch(
        "baserow.contrib.database.webhooks.tasks.enqueue_webhook_task"
    ) as mock_enqueue, patch(
        "baserow.contrib.database.webhooks.tasks.schedule_next_task_in_queue"
    ) as mock_schedule:
        call_webhook(
            webhook_id=webhook.id,
            event_id=event_id,
            event_type="test.paginated",
            method="POST",
            url="http://localhost/",
            headers={},
            payload={},
        )

        assert mock_enqueue.call_args[0][2] == expected_payload
        mock_schedule.assert_called_with(webhook.id)

    assert TableWebhookCall.objects.all().count() == 1
    assert TableWebhookCall.objects.filter(event_id=event_id).first().batch_id == 1

    # The second part of the payload exceeds the batch limit of 1. Therefore, it should
    # not send the data but should trigger a notification.
    enqueue_webhook_task(webhook.id, event_id, expected_payload, {})
    schedule_next_task_in_queue(webhook.id)

    # No new call should be made.
    assert TableWebhookCall.objects.all().count() == 1

    all_notifications = list(Notification.objects.all())
    assert len(all_notifications) == 1
    recipient_ids = [r.id for r in all_notifications[0].recipients.all()]
    assert recipient_ids == [admin_1.id, admin_2.id]
    assert all_notifications[0].type == WebhookPayloadTooLargeNotificationType.type
    assert all_notifications[0].broadcast is False
    assert all_notifications[0].workspace_id == workspace.id
    assert all_notifications[0].sender is None
    assert all_notifications[0].data == {
        "database_id": database.id,
        "table_id": table.id,
        "webhook_id": webhook.id,
        "webhook_name": webhook.name,
        "event_id": event_id,
        "batch_limit": 1,
    }

    # The webhook should still be active, but the queue should be empty.
    webhook.refresh_from_db()
    assert webhook.active is True

    with patch("baserow.contrib.database.webhooks.tasks.call_webhook.delay") as mock:
        schedule_next_task_in_queue(webhook.id)
        mock.assert_not_called()  # nothing else has been scheduled.

    assert TableWebhookCall.objects.all().count() == 1
