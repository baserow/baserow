from unittest.mock import MagicMock, patch

from django.test import override_settings

import pytest
import requests
import responses

from baserow.contrib.integrations.core.inbound_email import InboundEmailHandler
from baserow.contrib.integrations.core.inbound_email_receiver import (
    InboundEmailReceiverClient,
    InboundEmailReceiverError,
    InboundEmailReceiverStateHandler,
    sweep_inbound_email_receiver,
)
from baserow.contrib.integrations.core.models import CoreInboundEmailReceiverState

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


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=DOMAIN)
def test_webhook_records_the_high_water_mark_whatever_the_outcome():
    handler = InboundEmailHandler()

    # Unknown token: discarded, but the message exists on the receiver.
    payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}")
    payload["Meta"]["MsgID"] = 7
    handler.handle_webhook_payload(payload)
    assert InboundEmailReceiverStateHandler.get_state().last_seen_message_id == 7

    # Automated mail: discarded before any dispatch, still counted.
    payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}", MessageID="<auto@x>")
    payload["Meta"]["MsgID"] = 9
    payload["Meta"]["Automated"] = True
    handler.handle_webhook_payload(payload)
    assert InboundEmailReceiverStateHandler.get_state().last_seen_message_id == 9

    # A retried delivery with a lower id never moves the mark back.
    payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}", MessageID="<older@x>")
    payload["Meta"]["MsgID"] = 8
    handler.handle_webhook_payload(payload)
    assert InboundEmailReceiverStateHandler.get_state().last_seen_message_id == 9


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=DOMAIN)
def test_webhook_lowers_the_deleted_mark_when_an_already_swept_id_arrives():
    """
    Ids restart at 1 when the receiver's data directory is wiped. Without
    lowering the deleted mark the sweep would skip everything until the ids
    climbed past the old mark again, and the receiver would fill up.
    """

    state = InboundEmailReceiverStateHandler.get_state()
    state.last_seen_message_id = 5000
    state.last_deleted_message_id = 5000
    state.save()

    payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}")
    payload["Meta"]["MsgID"] = 3
    InboundEmailHandler().handle_webhook_payload(payload)

    state = InboundEmailReceiverStateHandler.get_state()
    assert state.last_deleted_message_id == 2
    # The seen mark still covers the old ids, so the next sweep cleans up both
    # the reset store and whatever the old one may still hold.
    assert state.last_seen_message_id == 5000

    # An id above the deleted mark, e.g. a first delivery, leaves it alone.
    payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}", MessageID="<next@x>")
    payload["Meta"]["MsgID"] = 4
    InboundEmailHandler().handle_webhook_payload(payload)
    assert InboundEmailReceiverStateHandler.get_state().last_deleted_message_id == 2


@pytest.mark.django_db
def test_webhook_ignores_a_missing_receiver_id():
    with override_settings(INBOUND_EMAIL_DOMAIN=DOMAIN):
        payload = make_mox_payload(f"{'a' * 32}@{DOMAIN}")
        payload["Meta"]["MsgID"] = 0
        InboundEmailHandler().handle_webhook_payload(payload)

    assert CoreInboundEmailReceiverState.objects.count() == 0


@pytest.mark.django_db
def test_sweep_closes_the_client_it_created_but_not_an_injected_one():
    InboundEmailReceiverStateHandler.record_seen_message(1)
    created = MagicMock()
    created.delete_message.return_value = True
    with patch.object(
        InboundEmailReceiverClient, "from_settings", return_value=created
    ):
        sweep_inbound_email_receiver()
    created.close.assert_called_once_with()

    injected = MagicMock()
    injected.delete_message.return_value = True
    InboundEmailReceiverStateHandler.record_seen_message(2)
    sweep_inbound_email_receiver(client=injected)
    injected.close.assert_not_called()


@pytest.mark.django_db
def test_sweep_is_a_no_op_when_not_configured():
    with override_settings(INBOUND_EMAIL_RECEIVER_URL=""):
        assert sweep_inbound_email_receiver() is None


@pytest.mark.django_db
def test_sweep_deletes_every_id_up_to_the_high_water_mark():
    InboundEmailReceiverStateHandler.record_seen_message(5)
    client = MagicMock()
    # Ids 1, 2 and 4 still exist on the receiver, 3 and 5 are already gone.
    client.delete_message.side_effect = [True, True, False, True, False]

    counts = sweep_inbound_email_receiver(client=client)

    assert [c.args[0] for c in client.delete_message.call_args_list] == [1, 2, 3, 4, 5]
    assert counts == {"deleted": 3, "already_gone": 2, "remaining": 0}
    assert InboundEmailReceiverStateHandler.get_state().last_deleted_message_id == 5


@pytest.mark.django_db
def test_sweep_resumes_after_the_last_deleted_id():
    InboundEmailReceiverStateHandler.record_seen_message(6)
    InboundEmailReceiverStateHandler.record_deleted_up_to(4)
    client = MagicMock()
    client.delete_message.return_value = True

    sweep_inbound_email_receiver(client=client)

    assert [c.args[0] for c in client.delete_message.call_args_list] == [5, 6]


@pytest.mark.django_db
def test_sweep_keeps_progress_when_the_receiver_fails_midway():
    InboundEmailReceiverStateHandler.record_seen_message(4)
    client = MagicMock()
    client.delete_message.side_effect = [
        True,
        True,
        InboundEmailReceiverError("down"),
        True,
    ]

    counts = sweep_inbound_email_receiver(client=client)

    assert counts == {"deleted": 2, "already_gone": 0, "remaining": 2}
    assert InboundEmailReceiverStateHandler.get_state().last_deleted_message_id == 2
    # The next run resumes with the id that failed.
    client.delete_message.side_effect = None
    client.delete_message.return_value = True
    client.delete_message.reset_mock()
    sweep_inbound_email_receiver(client=client)
    assert [c.args[0] for c in client.delete_message.call_args_list] == [3, 4]


@pytest.mark.django_db
def test_sweep_processes_at_most_max_messages_per_run():
    InboundEmailReceiverStateHandler.record_seen_message(10)
    client = MagicMock()
    client.delete_message.return_value = True

    counts = sweep_inbound_email_receiver(client=client, max_messages=4)

    assert [c.args[0] for c in client.delete_message.call_args_list] == [1, 2, 3, 4]
    assert counts["remaining"] == 6
    assert InboundEmailReceiverStateHandler.get_state().last_deleted_message_id == 4


@pytest.mark.django_db
def test_sweep_does_nothing_when_up_to_date():
    InboundEmailReceiverStateHandler.record_seen_message(3)
    InboundEmailReceiverStateHandler.record_deleted_up_to(3)
    client = MagicMock()

    assert sweep_inbound_email_receiver(client=client) == {
        "deleted": 0,
        "already_gone": 0,
        "remaining": 0,
    }
    client.delete_message.assert_not_called()


@pytest.mark.django_db
def test_celery_task_runs_the_sweep():
    from baserow.contrib.integrations.tasks import sweep_inbound_email_receiver as task

    with patch(
        "baserow.contrib.integrations.core.inbound_email_receiver.sweep_inbound_email_receiver"
    ) as mocked:
        task.apply()

    mocked.assert_called_once_with()
