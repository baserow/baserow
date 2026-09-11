from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import override_settings

import pytest
from loguru import logger

from baserow.contrib.integrations.core.exceptions import InvalidInboundEmailPayload
from baserow.contrib.integrations.core.inbound_email import (
    HANDLE_STATUS_ACCEPTED,
    HANDLE_STATUS_DISCARDED,
    HANDLE_STATUS_DUPLICATE,
    INBOUND_EMAIL_TEST_PREFIX,
    InboundEmail,
    InboundEmailAddress,
    InboundEmailHandler,
    InboundEmailTarget,
    normalize_mox_payload,
)

from .inbound_email_test_utils import make_mox_payload

INBOUND_DOMAIN = "inbound.test"
TOKEN = "a" * 32
ADDRESS = f"{TOKEN}@{INBOUND_DOMAIN}"
TEST_ADDRESS = f"{INBOUND_EMAIL_TEST_PREFIX}{TOKEN}@{INBOUND_DOMAIN}"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def inbound_email_logs():
    """
    Collects the loguru messages emitted by the handler so tests can assert on
    the outcome that operators see in the server log.
    """

    messages = []
    sink_id = logger.add(messages.append, level="INFO")
    yield messages
    logger.remove(sink_id)


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
    # The envelope recipient and its sub-address tag are exposed for routing.
    assert payload["rcpt_to"] == ADDRESS
    assert payload["recipient_tag"] == ""
    # The automation flag stays internal (used for loop protection only).
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
def test_extract_targets_prefers_rcpt_to():
    email = InboundEmail(rcpt_to=ADDRESS)
    assert InboundEmailHandler().extract_targets(email) == [InboundEmailTarget(TOKEN)]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_targets_falls_back_to_headers():
    other_token = "b" * 32
    email = InboundEmail(
        rcpt_to="",
        to=[InboundEmailAddress(address=f"someone@example.com")],
        cc=[InboundEmailAddress(address=f"{other_token}@{INBOUND_DOMAIN}")],
    )
    assert InboundEmailHandler().extract_targets(email) == [
        InboundEmailTarget(other_token)
    ]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_targets_multiple_and_deduplicated():
    other_token = "b" * 32
    email = InboundEmail(
        rcpt_to=ADDRESS,
        to=[
            InboundEmailAddress(address=ADDRESS),
            InboundEmailAddress(address=f"{other_token}@{INBOUND_DOMAIN}"),
        ],
    )
    assert InboundEmailHandler().extract_targets(email) == [
        InboundEmailTarget(TOKEN),
        InboundEmailTarget(other_token),
    ]


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
def test_extract_targets_rejects_invalid_recipients(address):
    email = InboundEmail(rcpt_to=address)
    assert InboundEmailHandler().extract_targets(email) == []


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_targets_is_case_insensitive():
    email = InboundEmail(rcpt_to=f"{TOKEN.upper()}@{INBOUND_DOMAIN.upper()}")
    assert InboundEmailHandler().extract_targets(email) == [InboundEmailTarget(TOKEN)]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_targets_strips_subaddress_tag():
    # `token+anything@domain` must resolve to the same `token` trigger.
    for tag in ["gmail", "hotmail", "with+extra+pluses", "MixedCase"]:
        email = InboundEmail(rcpt_to=f"{TOKEN}+{tag}@{INBOUND_DOMAIN}")
        assert InboundEmailHandler().extract_targets(email) == [
            InboundEmailTarget(TOKEN)
        ]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_targets_deduplicates_across_tags():
    # The same token reached via different tags must dispatch the trigger once.
    email = InboundEmail(
        rcpt_to=f"{TOKEN}+gmail@{INBOUND_DOMAIN}",
        to=[InboundEmailAddress(address=f"{TOKEN}+hotmail@{INBOUND_DOMAIN}")],
    )
    assert InboundEmailHandler().extract_targets(email) == [InboundEmailTarget(TOKEN)]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_tagged_recipient_full_mox_path():
    # Full wire-format path: a mox webhook for `token+bob@domain` resolves to the
    # `token` trigger and carries the tag through to the workflow payload.
    email = normalize_mox_payload(make_mox_payload(f"{TOKEN}+bob@{INBOUND_DOMAIN}"))
    assert InboundEmailHandler().extract_targets(email) == [InboundEmailTarget(TOKEN)]
    assert email.to_payload()["recipient_tag"] == "bob"


def test_to_payload_exposes_recipient_tag():
    payload = InboundEmail(rcpt_to=f"{TOKEN}+sales@{INBOUND_DOMAIN}").to_payload()
    assert payload["rcpt_to"] == f"{TOKEN}+sales@{INBOUND_DOMAIN}"
    # The tag is returned as received (case preserved) for exact routing.
    assert payload["recipient_tag"] == "sales"

    payload = InboundEmail(rcpt_to=f"{TOKEN}+Team-A@{INBOUND_DOMAIN}").to_payload()
    assert payload["recipient_tag"] == "Team-A"

    payload = InboundEmail(rcpt_to=f"{TOKEN}@{INBOUND_DOMAIN}").to_payload()
    assert payload["recipient_tag"] == ""


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_discards_automated_email():
    payload = make_mox_payload(ADDRESS)
    payload["Meta"]["Automated"] = True

    handler = InboundEmailHandler()
    with patch.object(handler, "_process_target") as mocked:
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
        payload = make_mox_payload(TEST_ADDRESS)

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
        payload = make_mox_payload(TEST_ADDRESS, MessageID="")
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
    payload = make_mox_payload(TEST_ADDRESS)

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


def _inbound_email_log(messages):
    (record,) = [str(m) for m in messages if "Inbound email" in str(m)]
    return record


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_logs_automated_discard(inbound_email_logs):
    payload = make_mox_payload(ADDRESS)
    payload["Meta"]["Automated"] = True

    InboundEmailHandler().handle_webhook_payload(payload)

    record = _inbound_email_log(inbound_email_logs)
    assert "Inbound email discarded: automated message" in record
    assert "token=-" in record


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_logs_no_matching_recipient(inbound_email_logs):
    InboundEmailHandler().handle_webhook_payload(
        make_mox_payload("someone@example.com")
    )

    record = _inbound_email_log(inbound_email_logs)
    assert "discarded: no recipient matches a trigger address" in record


@override_settings(INBOUND_EMAIL_DOMAIN="")
def test_handle_webhook_payload_logs_domain_not_configured(inbound_email_logs):
    InboundEmailHandler().handle_webhook_payload(make_mox_payload(ADDRESS))

    record = _inbound_email_log(inbound_email_logs)
    assert "discarded: inbound email domain not configured" in record


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_logs_unknown_token(inbound_email_logs):
    InboundEmailHandler().handle_webhook_payload(make_mox_payload(ADDRESS))

    record = _inbound_email_log(inbound_email_logs)
    assert "Inbound email discarded: no trigger for token" in record
    # Only a prefix of the token is logged; it is the trigger's routing secret.
    assert f"token={TOKEN[:8]}…" in record
    assert TOKEN not in record


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_logs_accepted_and_duplicate(
    data_fixture, inbound_email_logs
):
    data_fixture.create_inbound_email_trigger_node(service_kwargs={"token": TOKEN})

    from baserow.core.services.registries import service_type_registry

    service_type = service_type_registry.get("email_trigger")
    with patch.object(service_type, "on_event", MagicMock()):
        handler = InboundEmailHandler()
        payload = make_mox_payload(TEST_ADDRESS)
        handler.handle_webhook_payload(payload)
        handler.handle_webhook_payload(payload)

    first, second = [str(m) for m in inbound_email_logs if "Inbound email" in str(m)]
    assert "Inbound email accepted: dispatched to trigger" in first
    assert "Inbound email duplicate: message already processed" in second

    # Both deliveries of the same message share a reference so retries can be
    # correlated, and neither leaks the sender or recipient address.
    message_ref = first.split("message=")[1].split(",")[0]
    assert len(message_ref) == 12
    assert f"message={message_ref}" in second
    assert "ada@example.com" not in first
    assert ADDRESS not in first


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_targets_test_prefix_targets_the_draft():
    email = InboundEmail(rcpt_to=TEST_ADDRESS)

    assert InboundEmailHandler().extract_targets(email) == [
        InboundEmailTarget(TOKEN, simulate=True)
    ]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
@pytest.mark.parametrize(
    "rcpt_to",
    [
        f"TEST-{TOKEN.upper()}@{INBOUND_DOMAIN}",
        f"test-{TOKEN}+sales@{INBOUND_DOMAIN}",
        f"Test-{TOKEN}+Sales@{INBOUND_DOMAIN.upper()}",
    ],
)
def test_extract_targets_test_prefix_is_case_insensitive_and_keeps_tags(rcpt_to):
    email = InboundEmail(rcpt_to=rcpt_to)

    assert InboundEmailHandler().extract_targets(email) == [
        InboundEmailTarget(TOKEN, simulate=True)
    ]


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
@pytest.mark.parametrize(
    "rcpt_to",
    [
        f"test{TOKEN}@{INBOUND_DOMAIN}",
        f"test--{TOKEN}@{INBOUND_DOMAIN}",
        f"tset-{TOKEN}@{INBOUND_DOMAIN}",
        f"test-@{INBOUND_DOMAIN}",
    ],
)
def test_extract_targets_rejects_malformed_test_prefix(rcpt_to):
    email = InboundEmail(rcpt_to=rcpt_to)

    assert InboundEmailHandler().extract_targets(email) == []


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_extract_targets_keeps_test_and_published_addresses_apart():
    email = InboundEmail(
        rcpt_to=TEST_ADDRESS,
        to=[
            InboundEmailAddress(address=ADDRESS),
            InboundEmailAddress(address=TEST_ADDRESS),
        ],
    )

    assert InboundEmailHandler().extract_targets(email) == [
        InboundEmailTarget(TOKEN, simulate=True),
        InboundEmailTarget(TOKEN, simulate=False),
    ]


def test_dedupe_cache_key_differs_between_test_and_published_targets():
    handler = InboundEmailHandler()
    email = InboundEmail(message_id="<id@example.com>")

    published_key = handler.get_dedupe_cache_key(InboundEmailTarget(TOKEN), email)
    test_key = handler.get_dedupe_cache_key(
        InboundEmailTarget(TOKEN, simulate=True), email
    )

    assert published_key != test_key
    assert TOKEN in published_key and f"test-{TOKEN}" in test_key


@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_passes_simulate_to_the_service_type():
    from baserow.core.services.registries import service_type_registry

    service_type = service_type_registry.get("email_trigger")
    handler = InboundEmailHandler()

    with patch.object(service_type, "process_inbound_email") as mocked:
        assert (
            handler.handle_webhook_payload(make_mox_payload(TEST_ADDRESS))
            == HANDLE_STATUS_ACCEPTED
        )
        assert (
            handler.handle_webhook_payload(
                make_mox_payload(ADDRESS, MessageID="<other@example.com>")
            )
            == HANDLE_STATUS_ACCEPTED
        )

    (test_call, live_call) = mocked.call_args_list
    assert test_call.args[0] == TOKEN and test_call.kwargs == {"simulate": True}
    assert live_call.args[0] == TOKEN and live_call.kwargs == {"simulate": False}


@pytest.mark.django_db
@override_settings(INBOUND_EMAIL_DOMAIN=INBOUND_DOMAIN)
def test_handle_webhook_payload_logs_test_prefix(inbound_email_logs):
    InboundEmailHandler().handle_webhook_payload(make_mox_payload(TEST_ADDRESS))

    record = _inbound_email_log(inbound_email_logs)
    assert f"token=test-{TOKEN[:8]}…" in record
