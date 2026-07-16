from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import override_settings

import pytest

from baserow.contrib.integrations.core.exceptions import InvalidInboundEmailPayload
from baserow.contrib.integrations.core.inbound_email import (
    HANDLE_STATUS_ACCEPTED,
    HANDLE_STATUS_DISCARDED,
    HANDLE_STATUS_DUPLICATE,
    InboundEmail,
    InboundEmailAddress,
    InboundEmailHandler,
    normalize_mox_payload,
)

from .inbound_email_test_utils import make_mox_payload

INBOUND_DOMAIN = "inbound.test"
TOKEN = "a" * 32
ADDRESS = f"{TOKEN}@{INBOUND_DOMAIN}"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


def test_normalize_mox_payload():
    email = normalize_mox_payload(make_mox_payload(ADDRESS))

    assert email.from_ == InboundEmailAddress(
        name="Ada Lovelace", address="ada@example.com"
    )
    assert email.to == [InboundEmailAddress(name="", address=ADDRESS)]
    assert email.cc == []
    assert email.reply_to == [
        InboundEmailAddress(name="Ada Lovelace", address="ada@example.com")
    ]
    assert email.subject == "Hello from Ada"
    assert email.body_text == "Hi there,\n\nThis is the plain text body.\n"
    assert email.body_html == "<p>Hi there,</p><p>This is the HTML body.</p>"
    assert email.message_id == "<unique-id-123@example.com>"
    assert email.in_reply_to == ""
    assert email.received_at == "2026-07-15T12:00:01Z"
    assert len(email.attachments) == 1
    assert email.attachments[0].filename == "invoice.pdf"
    assert email.attachments[0].content_type == "application/pdf"
    assert email.attachments[0].size == 12345
    assert email.sender_validated is True
    assert email.dkim_verified_domains == ["example.com"]
    assert email.remote_ip == "203.0.113.10"
    assert email.rcpt_to == ADDRESS
    assert email.is_automated is False
    assert email.internal_message_id == "42"


def test_normalize_mox_payload_to_payload():
    payload = normalize_mox_payload(make_mox_payload(ADDRESS)).to_payload()

    assert payload["from"] == {"name": "Ada Lovelace", "address": "ada@example.com"}
    assert payload["to"] == [{"name": "", "address": ADDRESS}]
    assert payload["subject"] == "Hello from Ada"
    assert payload["attachments"] == [
        {"filename": "invoice.pdf", "content_type": "application/pdf", "size": 12345}
    ]
    assert payload["sender_validated"] is True
    assert payload["dkim_verified_domains"] == ["example.com"]
    # The envelope recipient and automation flags are internal and not part of
    # the payload exposed to workflows.
    assert "rcpt_to" not in payload
    assert "is_automated" not in payload


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "a string",
        {},
        {"From": []},
        {"Meta": {}},
        {"From": "not-a-list", "Meta": {}},
        {"From": [], "Meta": "not-a-dict"},
    ],
)
def test_normalize_mox_payload_invalid(data):
    with pytest.raises(InvalidInboundEmailPayload):
        normalize_mox_payload(data)


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_tokens_prefers_rcpt_to():
    email = InboundEmail(rcpt_to=ADDRESS)
    assert InboundEmailHandler().extract_tokens(email) == [TOKEN]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_tokens_falls_back_to_headers():
    other_token = "b" * 32
    email = InboundEmail(
        rcpt_to="",
        to=[InboundEmailAddress(address=f"someone@example.com")],
        cc=[InboundEmailAddress(address=f"{other_token}@{INBOUND_DOMAIN}")],
    )
    assert InboundEmailHandler().extract_tokens(email) == [other_token]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_tokens_multiple_and_deduplicated():
    other_token = "b" * 32
    email = InboundEmail(
        rcpt_to=ADDRESS,
        to=[
            InboundEmailAddress(address=ADDRESS),
            InboundEmailAddress(address=f"{other_token}@{INBOUND_DOMAIN}"),
        ],
    )
    assert InboundEmailHandler().extract_tokens(email) == [TOKEN, other_token]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
@pytest.mark.parametrize(
    "address",
    [
        f"{TOKEN}@other-domain.test",
        f"not-a-token@{INBOUND_DOMAIN}",
        f"{'A' * 31}@{INBOUND_DOMAIN}",
        "no-at-sign",
        "",
    ],
)
def test_extract_tokens_rejects_invalid_recipients(address):
    email = InboundEmail(rcpt_to=address)
    assert InboundEmailHandler().extract_tokens(email) == []


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_tokens_is_case_insensitive():
    email = InboundEmail(rcpt_to=f"{TOKEN.upper()}@{INBOUND_DOMAIN.upper()}")
    assert InboundEmailHandler().extract_tokens(email) == [TOKEN]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_discards_automated_email():
    payload = make_mox_payload(ADDRESS)
    payload["Meta"]["Automated"] = True

    handler = InboundEmailHandler()
    with patch.object(handler, "_process_token") as mocked:
        assert handler.handle_webhook_payload(payload) == HANDLE_STATUS_DISCARDED

    mocked.assert_not_called()


@override_settings(INBOUND_EMAIL_DOMAIN="")
def test_handle_webhook_payload_discards_when_domain_not_configured():
    handler = InboundEmailHandler()
    assert (
        handler.handle_webhook_payload(make_mox_payload(ADDRESS))
        == HANDLE_STATUS_DISCARDED
    )


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_discards_when_no_token_matches():
    handler = InboundEmailHandler()
    assert (
        handler.handle_webhook_payload(make_mox_payload("someone@example.com"))
        == HANDLE_STATUS_DISCARDED
    )


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_discards_unknown_token():
    handler = InboundEmailHandler()
    assert (
        handler.handle_webhook_payload(make_mox_payload(ADDRESS))
        == HANDLE_STATUS_DISCARDED
    )


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_accepts_and_deduplicates(data_fixture):
    node = data_fixture.create_inbound_email_trigger_node(
        service_kwargs={"token": TOKEN}
    )

    from baserow.core.services.registries import service_type_registry

    service_type = service_type_registry.get("email_trigger")
    with patch.object(service_type, "on_event", MagicMock()) as mocked:
        handler = InboundEmailHandler()
        payload = make_mox_payload(ADDRESS)

        assert handler.handle_webhook_payload(payload) == HANDLE_STATUS_ACCEPTED
        assert mocked.call_count == 1

        services, event_payload = mocked.call_args.args
        assert services == [node.service.specific]
        assert event_payload(node.service)["subject"] == "Hello from Ada"

        # A retried delivery of the same message must be idempotent.
        assert handler.handle_webhook_payload(payload) == HANDLE_STATUS_DUPLICATE
        assert mocked.call_count == 1


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_skips_dedupe_without_message_id(data_fixture):
    data_fixture.create_inbound_email_trigger_node(service_kwargs={"token": TOKEN})

    from baserow.core.services.registries import service_type_registry

    service_type = service_type_registry.get("email_trigger")
    with patch.object(service_type, "on_event", MagicMock()) as mocked:
        handler = InboundEmailHandler()
        payload = make_mox_payload(ADDRESS, MessageID="")
        payload["Meta"]["MsgID"] = 0

        assert handler.handle_webhook_payload(payload) == HANDLE_STATUS_ACCEPTED
        assert handler.handle_webhook_payload(payload) == HANDLE_STATUS_ACCEPTED
        assert mocked.call_count == 2


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_removes_dedupe_entry_on_error(data_fixture):
    data_fixture.create_inbound_email_trigger_node(service_kwargs={"token": TOKEN})

    from baserow.core.services.registries import service_type_registry

    service_type = service_type_registry.get("email_trigger")
    handler = InboundEmailHandler()
    payload = make_mox_payload(ADDRESS)

    with patch.object(
        service_type, "on_event", MagicMock(side_effect=Exception("boom"))
    ):
        with pytest.raises(Exception, match="boom"):
            handler.handle_webhook_payload(payload)

    # The failed delivery must not poison the dedupe cache; the retried
    # delivery is processed normally.
    with patch.object(service_type, "on_event", MagicMock()) as mocked:
        assert handler.handle_webhook_payload(payload) == HANDLE_STATUS_ACCEPTED

    mocked.assert_called_once()
