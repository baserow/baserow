from collections import defaultdict
from unittest.mock import MagicMock, patch

from django.db import transaction
from django.test import override_settings

import httpretty
import pytest
import responses
from celery.exceptions import Retry

from baserow.contrib.database.webhooks.models import TableWebhook, TableWebhookCall
from baserow.contrib.database.webhooks.tasks import call_webhook
from baserow.core.redis import RedisQueue
from baserow.test_utils.helpers import stub_getaddrinfo


class MemoryQueue(RedisQueue):
    queues = defaultdict(list)

    def enqueue_task(self, task_object):
        self.queues[self.queue_key].append(task_object)
        return True

    def get_and_pop_next(self):
        try:
            self.queues[self.queue_key].pop(0)
        except IndexError:
            return None

    def clear(self):
        self.queues[self.queue_key] = []


@pytest.mark.django_db(transaction=True)
@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL=1,
    BASEROW_WEBHOOKS_MAX_CONSECUTIVE_TRIGGER_FAILURES=1,
)
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
@patch("baserow.contrib.database.webhooks.tasks.RedisQueue", MemoryQueue)
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
