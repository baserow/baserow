import json
from unittest.mock import MagicMock, call, patch
from urllib.parse import parse_qs

from django.test import override_settings

import pytest
import requests
import responses
from celery.exceptions import Retry

from baserow.contrib.integrations.core.inbound_email import InboundEmailHandler
from baserow.contrib.integrations.core.inbound_email_receiver import (
    INBOUND_EMAIL_RECEIVER_DELETE_DELAY_SECONDS,
    InboundEmailReceiverClient,
    InboundEmailReceiverError,
    delete_receiver_message,
)
from baserow.contrib.integrations.tasks import (
    delete_inbound_email_receiver_message as delete_task,
)

from .inbound_email_test_utils import make_mox_payload

RECEIVER = "http://email-receiver:8880"
DOMAIN = "inbound.test"
SECRET = "a-long-webhook-secret"
DELETE_URL = f"{RECEIVER}/webapi/v0/MessageDelete"


def make_client():
    return InboundEmailReceiverClient(RECEIVER, f"webapi@{DOMAIN}", SECRET)


@responses.activate
def test_client_deletes_a_message_with_the_web_api_request_shape():
    responses.add(responses.POST, DELETE_URL, json={}, status=200)

    assert make_client().delete_message(42) is True

    request = responses.calls[0].request
    # Mox expects a form field `request` holding JSON, and HTTP basic auth with
    # an address of the account.
    assert request.body == "request=%7B%22MsgID%22%3A+42%7D"
    assert request.headers["Authorization"].startswith("Basic ")
    # Mox only serves the web API for requests addressed to an IP, its own
    # hostname or "localhost"; the compose deployments reach it by service
    # name, so the client must not send that name as the Host header.
    assert request.headers["Host"] == "localhost"


def test_client_reuses_one_session_and_closes_it():
    client = make_client()
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=200)
    client._session = session

    assert client.delete_message(1) is True
    assert client.delete_message(2) is True

    assert session.post.call_count == 2
    client.close()
    session.close.assert_called_once_with()


@responses.activate
@pytest.mark.parametrize(
    "error",
    [
        {"Code": "messageNotFound", "Message": "getting message: no such message"},
        {"Code": "user", "Message": "getting message: message was removed"},
    ],
)
def test_client_reports_missing_or_removed_messages_as_gone(error):
    responses.add(responses.POST, DELETE_URL, json=error, status=400)

    assert make_client().delete_message(42) is False


@responses.activate
@pytest.mark.parametrize(
    "status,body",
    [
        (401, "unauthorized"),
        (400, '{"Code": "protocol", "Message": "missing/empty request"}'),
        (500, "boom"),
    ],
)
def test_client_raises_on_other_failures(status, body):
    responses.add(responses.POST, DELETE_URL, body=body, status=status)

    with pytest.raises(InboundEmailReceiverError):
        make_client().delete_message(42)


@responses.activate
def test_client_raises_when_the_receiver_is_unreachable():
    responses.add(responses.POST, DELETE_URL, body=requests.ConnectionError("down"))

    with pytest.raises(InboundEmailReceiverError):
        make_client().delete_message(42)


@override_settings(
    INBOUND_EMAIL_RECEIVER_URL=RECEIVER,
    INBOUND_EMAIL_DOMAIN=DOMAIN,
    INBOUND_EMAIL_WEBHOOK_SECRET=SECRET,
)
def test_client_from_settings_authenticates_as_the_webapi_address():
    client = InboundEmailReceiverClient.from_settings()

    assert client.base_url == RECEIVER
    assert client.username == f"webapi@{DOMAIN}"
    assert client.password == SECRET


@pytest.mark.parametrize(
    "overrides",
    [
        {"INBOUND_EMAIL_RECEIVER_URL": ""},
        {"INBOUND_EMAIL_DOMAIN": ""},
        {"INBOUND_EMAIL_WEBHOOK_SECRET": ""},
    ],
)
def test_client_from_settings_is_none_when_not_configured(overrides):
    values = {
        "INBOUND_EMAIL_RECEIVER_URL": RECEIVER,
        "INBOUND_EMAIL_DOMAIN": DOMAIN,
        "INBOUND_EMAIL_WEBHOOK_SECRET": SECRET,
        **overrides,
    }
    with override_settings(**values):
        assert InboundEmailReceiverClient.from_settings() is None


CONFIGURED = dict(
    INBOUND_EMAIL_DOMAIN=DOMAIN,
    INBOUND_EMAIL_WEBHOOK_SECRET=SECRET,
    INBOUND_EMAIL_RECEIVER_URL=RECEIVER,
)


def deleted_ids(request_calls):
    return [
        json.loads(parse_qs(c.request.body)["request"][0])["MsgID"]
        for c in request_calls
    ]


@pytest.mark.django_db
@override_settings(**CONFIGURED)
def test_webhook_queues_the_deletion_of_every_received_message(
    django_capture_on_commit_callbacks,
):
    handler = InboundEmailHandler()

    with patch.object(delete_task, "apply_async") as apply_async:
        # Unknown token: discarded, but the message exists on the receiver.
        payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}")
        payload["Meta"]["MsgID"] = 7
        with django_capture_on_commit_callbacks(execute=True):
            handler.handle_webhook_payload(payload)

        # Automated mail: discarded before any dispatch, still deleted.
        payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}", MessageID="<auto@x>")
        payload["Meta"]["MsgID"] = 9
        payload["Meta"]["Automated"] = True
        with django_capture_on_commit_callbacks(execute=True):
            handler.handle_webhook_payload(payload)

    assert apply_async.call_args_list == [
        call(args=[7], countdown=INBOUND_EMAIL_RECEIVER_DELETE_DELAY_SECONDS),
        call(args=[9], countdown=INBOUND_EMAIL_RECEIVER_DELETE_DELAY_SECONDS),
    ]


@pytest.mark.django_db
@override_settings(**CONFIGURED)
def test_webhook_queues_the_deletion_only_once_the_request_commits(
    django_capture_on_commit_callbacks,
):
    """
    The deletion must not race the webhook it belongs to: it is queued from an
    on-commit hook, so a failing request (which mox retries) queues nothing.
    """

    payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}")
    payload["Meta"]["MsgID"] = 7

    with patch.object(delete_task, "apply_async") as apply_async:
        with django_capture_on_commit_callbacks() as callbacks:
            InboundEmailHandler().handle_webhook_payload(payload)
        apply_async.assert_not_called()

    assert len(callbacks) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "message_id,receiver_url",
    [
        # Mox always sends an id; a missing one is nothing to delete.
        (0, RECEIVER),
        # No receiver to delete from, so nothing is queued at all.
        (7, ""),
    ],
)
def test_webhook_queues_no_deletion_when_there_is_nothing_to_delete(
    django_capture_on_commit_callbacks, message_id, receiver_url
):
    payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}")
    payload["Meta"]["MsgID"] = message_id

    with override_settings(
        **{**CONFIGURED, "INBOUND_EMAIL_RECEIVER_URL": receiver_url}
    ):
        with patch.object(delete_task, "apply_async") as apply_async:
            with django_capture_on_commit_callbacks(execute=True):
                InboundEmailHandler().handle_webhook_payload(payload)

    apply_async.assert_not_called()


@responses.activate
@override_settings(**CONFIGURED)
def test_delete_task_deletes_the_message_from_the_receiver():
    responses.add(responses.POST, DELETE_URL, json={}, status=200)

    delete_task.apply(args=[7])

    assert deleted_ids(responses.calls) == [7]


@responses.activate
@override_settings(**CONFIGURED)
def test_delete_task_treats_an_already_gone_message_as_done():
    # A retried webhook queues a second deletion of the same message.
    responses.add(
        responses.POST,
        DELETE_URL,
        json={"Code": "messageNotFound", "Message": "message not found"},
        status=400,
    )

    result = delete_task.apply(args=[7])

    assert result.successful()
    assert len(responses.calls) == 1


@responses.activate
def test_delete_task_is_a_no_op_when_no_receiver_is_configured():
    with override_settings(**{**CONFIGURED, "INBOUND_EMAIL_RECEIVER_URL": ""}):
        assert delete_receiver_message(7) is None
        result = delete_task.apply(args=[7])

    assert result.successful()
    assert len(responses.calls) == 0


@responses.activate
@override_settings(**CONFIGURED)
def test_delete_task_retries_with_backoff_while_the_receiver_cannot_be_used():
    responses.add(responses.POST, DELETE_URL, status=502, body="bad gateway")

    # Eagerly, the retry surfaces as the Retry exception a worker would act on.
    with pytest.raises(Retry) as retry:
        delete_task.apply(args=[7])

    assert isinstance(retry.value.exc, InboundEmailReceiverError)
    assert len(responses.calls) == 1
    # Exponential backoff from a minute, capped at an hour, for a few hours.
    assert delete_task.max_retries == 8
    assert delete_task.retry_backoff == 60
    assert delete_task.retry_backoff_max == 60 * 60


@responses.activate
@override_settings(**CONFIGURED)
def test_delete_receiver_message_closes_the_client():
    responses.add(responses.POST, DELETE_URL, json={}, status=200)

    with patch.object(InboundEmailReceiverClient, "close") as close:
        assert delete_receiver_message(7) is True

    close.assert_called_once_with()
