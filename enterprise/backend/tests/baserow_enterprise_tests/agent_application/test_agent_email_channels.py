from unittest.mock import patch

from django.core import mail
from django.test import override_settings

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.integrations.core.inbound_email import InboundEmailHandler
from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.approval_preview import (
    build_approval_preview,
)
from baserow_enterprise.agent_application.channels.email import (
    EmailReplyNotPossible,
    HostedEmailAgentChatChannelType,
    ReceivedEmail,
)
from baserow_enterprise.agent_application.channels.email_text import (
    html_to_text,
    normalize_subject,
    strip_quoted_reply,
)
from baserow_enterprise.agent_application.channels.mailbox import (
    GmailAgentChatChannelType,
    OutlookAgentChatChannelType,
    poll_mailbox_channels,
)
from baserow_enterprise.agent_application.channels.registries import (
    start_channel_chat,
)
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatChannel,
    AgentChatMessage,
    AgentEmailMessage,
)
from baserow_enterprise.agent_application.tools.gating import (
    ApprovalRequiredToolset,
)

from .test_agent_runner import register_runner_test_model_type

DOMAIN = "agents.example.com"
INBOUND = dict(
    INBOUND_EMAIL_DOMAIN=DOMAIN,
    INBOUND_EMAIL_WEBHOOK_SECRET="secret-secret",
    INBOUND_EMAIL_RECEIVER_URL="http://receiver:8880",
    FROM_EMAIL="no-reply@example.com",
)
TASK = "baserow_enterprise.agent_application.tasks.process_agent_channel_message.delay"
SMTP_OK = (
    "baserow.contrib.integrations.core.service_types.CoreSMTPEmailServiceType"
    ".instance_smtp_unavailable_reason"
)
MAILBOX_REQUEST = "baserow_enterprise.agent_application.channels.mailbox._json_request"


def make_mox_payload(rcpt_to, **overrides):
    """A mox `webhook.Incoming` delivery, the shape the receiver posts."""

    payload = {
        "From": [{"Name": "Sender", "Address": "sender@example.com"}],
        "To": [{"Name": "", "Address": rcpt_to}],
        "CC": [],
        "ReplyTo": [],
        "Subject": "Hello",
        "Text": "Body",
        "HTML": "",
        "MessageID": "<unique-id-123@example.com>",
        "InReplyTo": "",
        "References": [],
        "Structure": {"ContentType": "text/plain", "Parts": []},
        "Meta": {
            "MsgID": 1,
            "Received": "2026-10-07T08:00:00Z",
            "MsgFromValidated": True,
            "DKIMVerifiedDomains": ["example.com"],
            "RemoteIP": "203.0.113.5",
            "RcptTo": rcpt_to,
            "Automated": False,
        },
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def email_setup(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Help")
        .specific
    )
    application.active = True
    application.save(update_fields=["active"])
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent, ai_generative_ai_type="agent_runner_test", ai_generative_ai_model="m"
    )
    return user, application, agent


def _hosted_channel(application, **config):
    with override_settings(**INBOUND):
        prepared = HostedEmailAgentChatChannelType().prepare_config(
            {"localpart": "support", **config}
        )
    return AgentChatChannel.objects.create(
        application=application, type="email", name="Support mail", config=prepared
    )


def test_quoted_replies_and_subjects_are_normalized():
    assert (
        strip_quoted_reply(
            "Thanks, that works!\n\nOn Mon, Oct 6, 2026 at 9:00 AM Help <help@x.com> "
            "wrote:\n> Hello\n> Try this"
        )
        == "Thanks, that works!"
    )
    assert strip_quoted_reply("Yes please\n\n> earlier\n> lines\n") == "Yes please"
    assert strip_quoted_reply("Done.\n-- \nAnn\nCEO") == "Done."
    assert (
        strip_quoted_reply(
            "Ok\n\nFrom: Help <help@x.com>\nSent: Monday\nTo: me\nSubject: Re: x\n\nold"
        )
        == "Ok"
    )
    assert html_to_text("<p>Hi<br>there</p><style>x{}</style>&amp; bye") == (
        "Hi\nthere\n& bye"
    )
    assert normalize_subject("RE: Fwd: Re: Order 12 ") == "order 12"
    assert normalize_subject("Order 12") == "order 12"


@pytest.mark.django_db
@override_settings(**INBOUND)
def test_hosted_channel_config_validates_the_address(email_setup):
    user, application, agent = email_setup
    channel_type = HostedEmailAgentChatChannelType()
    config = channel_type.prepare_config({})
    assert len(config["token"]) == 32
    assert config["localpart"] == ""
    assert config["require_approval"] is True
    assert config["allowed_sender_domains"] == []

    with pytest.raises(ValidationError):
        channel_type.prepare_config({"localpart": "Bad Address!"})
    with pytest.raises(ValidationError):
        channel_type.prepare_config({"localpart": "postmaster"})
    with pytest.raises(ValidationError):
        channel_type.prepare_config({"localpart": "test-support"})

    channel = _hosted_channel(application, allowed_sender_domains="Example.com, x.org")
    assert channel.config["allowed_sender_domains"] == ["example.com", "x.org"]
    assert channel_type.address(channel) == f"support@{DOMAIN}"

    # Another agent cannot take the same address; the channel itself can keep it.
    with pytest.raises(ValidationError):
        channel_type.prepare_config({"localpart": "support"})
    kept = channel_type.prepare_config(
        {"localpart": "support"}, existing_config=channel.config
    )
    assert kept["token"] == channel.config["token"]

    # A copy must not answer to the original's address.
    copied = channel_type.prepare_imported_config(channel.config)
    assert copied["localpart"] == "" and copied["token"] != channel.config["token"]

    public = channel_type.get_public_config(channel)
    assert public["address"] == f"support@{DOMAIN}"
    assert public["inbound_configured"] is True

    with pytest.raises(ValidationError):
        channel_type.prepare_config({"smtp_integration_id": 5})


@pytest.mark.django_db
def test_hosted_channel_needs_inbound_email_configured(email_setup):
    with pytest.raises(ValidationError) as exc:
        HostedEmailAgentChatChannelType().prepare_config({})
    assert "not configured" in str(exc.value)


@pytest.mark.django_db
@override_settings(**INBOUND)
def test_inbound_mail_routes_to_the_channel_and_maps_replies(email_setup):
    user, application, agent = email_setup
    channel = _hosted_channel(application)
    handler = InboundEmailHandler()

    with patch(TASK) as delay:
        status = handler.handle_webhook_payload(
            make_mox_payload(
                f"support@{DOMAIN}",
                MessageID="<m1@customer.example>",
                Subject="Order 12 is late",
                Text="Where is my order?\n\n-- \nAnn",
                From=[{"Name": "Ann", "Address": "ann@customer.example"}],
            )
        )
    assert status == "accepted"
    delay.assert_called_once()
    channel_id, session_key, text, sender_name, attachments, title = (
        delay.call_args.args
    )
    assert channel_id == channel.id
    assert len(session_key) == 12
    assert text.startswith(
        "From: Ann <ann@customer.example>\nSubject: Order 12 is late"
    )
    assert text.endswith("Where is my order?")
    assert title == "Email: Order 12 is late"
    record = AgentEmailMessage.objects.get(channel=channel)
    assert record.session_key == session_key
    assert record.direction == "inbound"
    assert record.message_id == "<m1@customer.example>"

    # The same delivery again is a duplicate.
    with patch(TASK) as delay:
        assert (
            handler.handle_webhook_payload(
                make_mox_payload(f"support@{DOMAIN}", MessageID="<m1@customer.example>")
            )
            == "duplicate"
        )
    delay.assert_not_called()

    # The conversation exists once the task ran; later mail must find it.
    chat = AgentChat.objects.create(
        agent=agent,
        source=AgentChat.Source.CHANNEL,
        channel=channel,
        channel_session_key=session_key,
    )
    channel_type = HostedEmailAgentChatChannelType()

    # 1. By the reply address tag.
    assert (
        channel_type.find_session_key(
            channel,
            ReceivedEmail(
                from_address="ann@customer.example", recipient_tag=session_key
            ),
        )
        == session_key
    )
    # 2. By the threading headers, including a reference deep in the chain.
    assert (
        channel_type.find_session_key(
            channel,
            ReceivedEmail(
                from_address="other@customer.example",
                references=["<x@y>", "<m1@customer.example>"],
            ),
        )
        == session_key
    )
    # 3. By the same sender and subject within the window.
    assert (
        channel_type.find_session_key(
            channel,
            ReceivedEmail(
                from_address="Ann@Customer.example", subject="Re: order 12 is late"
            ),
        )
        == session_key
    )
    # Nothing in common: a new conversation.
    assert (
        channel_type.find_session_key(
            channel, ReceivedEmail(from_address="bob@other.example", subject="Hi")
        )
        is None
    )

    # Mail the channel sent itself, and senders outside the allowed domains,
    # are ignored.
    assert (
        channel_type.receive_email(
            channel, ReceivedEmail(from_address="no-reply@example.com", subject="x")
        )
        is False
    )
    channel.config["allowed_sender_domains"] = ["customer.example"]
    assert (
        channel_type.receive_email(
            channel, ReceivedEmail(from_address="eve@evil.example", subject="x")
        )
        is False
    )
    assert chat.id


@pytest.mark.django_db
@override_settings(
    **INBOUND, CELERY_EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
def test_hosted_reply_threads_and_records_the_message(email_setup):
    user, application, agent = email_setup
    channel = _hosted_channel(application, from_name="Help desk")
    channel_type = HostedEmailAgentChatChannelType()
    channel_type.receive_email(
        channel,
        ReceivedEmail(
            from_address="ann@customer.example",
            from_name="Ann",
            subject="Order 12 is late",
            message_id="<m1@customer.example>",
            references=["<m0@customer.example>"],
            text="Where is it?",
        ),
    )
    session_key = AgentEmailMessage.objects.get(channel=channel).session_key
    chat = AgentChat.objects.create(
        agent=agent,
        source=AgentChat.Source.CHANNEL,
        channel=channel,
        channel_session_key=session_key,
    )

    with patch(SMTP_OK, return_value=None):
        sent = channel_type.reply(channel, chat, "It ships tomorrow.\n\nHelp desk")

    assert sent == {"to": "ann@customer.example", "subject": "Re: Order 12 is late"}
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["ann@customer.example"]
    assert message.from_email == "Help desk <no-reply@example.com>"
    assert message.reply_to == [f"support+{session_key}@{DOMAIN}"]
    assert message.extra_headers["In-Reply-To"] == "<m1@customer.example>"
    assert message.extra_headers["References"] == (
        "<m0@customer.example> <m1@customer.example>"
    )
    assert message.extra_headers["Message-ID"].endswith(f"@{DOMAIN}>")
    assert message.body == "It ships tomorrow.\n\nHelp desk"

    outbound = AgentEmailMessage.objects.get(channel=channel, direction="outbound")
    assert outbound.message_id == message.extra_headers["Message-ID"]
    assert outbound.session_key == session_key
    # Ann answering our message maps back, by our own Message-ID.
    assert (
        channel_type.find_session_key(
            channel,
            ReceivedEmail(
                from_address="ann@customer.example", in_reply_to=outbound.message_id
            ),
        )
        == session_key
    )

    empty = AgentChat.objects.create(
        agent=agent,
        source=AgentChat.Source.CHANNEL,
        channel=channel,
        channel_session_key="nobody",
    )
    with pytest.raises(EmailReplyNotPossible):
        channel_type.reply(channel, empty, "hi")


@pytest.mark.django_db
@override_settings(**INBOUND)
def test_email_channel_hooks_keep_outsiders_out_of_the_loop(email_setup):
    user, application, agent = email_setup
    channel = _hosted_channel(application)
    channel_type = HostedEmailAgentChatChannelType()
    with patch(TASK):
        channel_type.receive_email(
            channel,
            ReceivedEmail(
                from_address="ann@customer.example", subject="Hi", text="Hello"
            ),
        )
    session_key = AgentEmailMessage.objects.get(channel=channel).session_key

    with patch("baserow_enterprise.agent_application.tasks.run_agent_chat"):
        message = start_channel_chat(
            channel, session_key, "From: ann\n\nHello", title="Email: Hi"
        )
    chat = message.chat
    assert chat.title == "Email: Hi"
    assert chat.channel_session_key == session_key

    # The reply tool is there, behind the approval queue by default.
    toolsets = channel_type.get_toolsets(channel, chat)
    assert len(toolsets) == 1 and isinstance(toolsets[0], ApprovalRequiredToolset)
    channel.config["require_approval"] = False
    assert not isinstance(
        channel_type.get_toolsets(channel, chat)[0], ApprovalRequiredToolset
    )

    # Run outcomes are never mailed to the person.
    channel_type.deliver_outcome(channel, chat, AgentChat.Status.ERROR, "oops")
    channel_type.deliver_outcome(channel, chat, AgentChat.Status.IDLE, "answer")
    assert (
        AgentEmailMessage.objects.filter(channel=channel, direction="outbound").count()
        == 0
    )

    # A mail during an approval is kept for the reviewer instead of refused.
    chat.status = AgentChat.Status.AWAITING_APPROVAL
    chat.save(update_fields=["status"])
    assert start_channel_chat(channel, session_key, "From: ann\n\nStill there?") is None
    assert chat.messages.filter(role=AgentChatMessage.Role.HUMAN).count() == 2

    preview = build_approval_preview(chat, None, "reply_by_email", {"body": "Yes!"})
    assert preview == {
        "kind": "email",
        "body": "Yes!",
        "to": "ann@customer.example",
        "subject": "Re: Hi",
    }
    assert channel_type.get_system_notes(channel)[0].startswith(
        "This conversation is an email thread"
    )


@pytest.mark.django_db
def test_gmail_channel_polls_the_label_and_replies_in_the_thread(
    email_setup, data_fixture
):
    user, application, agent = email_setup
    integration = data_fixture.create_google_integration(
        application=application, account_email="help@company.example"
    )
    channel_type = GmailAgentChatChannelType()
    config = channel_type.prepare_config(
        {"integration_id": integration.id, "label": "Agent", "alias": ""}
    )
    channel = AgentChatChannel.objects.create(
        application=application, type="gmail", name="Gmail", config=config
    )
    token = patch(
        "baserow_enterprise.agent_application.channels.mailbox"
        ".OAuth2IntegrationHandler.get_access_token",
        return_value="at",
    )

    # First poll only takes note of where the mailbox is.
    with token, patch(MAILBOX_REQUEST, return_value=(200, {"historyId": "100"})):
        poll_mailbox_channels()
    channel.refresh_from_db()
    assert channel.config["cursor"] == "100"

    def b64(text):
        import base64

        return base64.urlsafe_b64encode(text.encode()).decode()

    responses = {
        "labels": (200, {"labels": [{"id": "Label_7", "name": "Agent"}]}),
        "history": (
            200,
            {
                "historyId": "120",
                "history": [
                    {
                        "messagesAdded": [
                            {"message": {"id": "msg1", "labelIds": ["INBOX"]}}
                        ]
                    },
                    {
                        "messagesAdded": [
                            {"message": {"id": "sent1", "labelIds": ["SENT"]}}
                        ]
                    },
                ],
            },
        ),
        "messages/msg1": (
            200,
            {
                "id": "msg1",
                "threadId": "thread-1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Ann <ann@customer.example>"},
                        {"name": "To", "value": "help@company.example"},
                        {"name": "Subject", "value": "Invoice"},
                        {"name": "Message-ID", "value": "<g1@mail.gmail.com>"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": b64("Please resend.")},
                        },
                        {
                            "mimeType": "application/pdf",
                            "filename": "invoice.pdf",
                            "body": {"attachmentId": "att1"},
                        },
                    ],
                },
            },
        ),
        "attachments/att1": (200, {"data": b64("%PDF-1.4 fake")}),
    }

    def fake_request(method, url, headers, params=None, json=None):
        for key, answer in responses.items():
            if url.endswith(key):
                assert headers["Authorization"] == "Bearer at"
                return answer
        raise AssertionError(f"unexpected request {method} {url}")

    with token, patch(MAILBOX_REQUEST, side_effect=fake_request), patch(TASK) as delay:
        poll_mailbox_channels()

    channel.refresh_from_db()
    assert channel.config["cursor"] == "120"
    assert channel.config["label_id"] == "Label_7"
    delay.assert_called_once()
    _, session_key, text, _, attachments, title = delay.call_args.args
    assert session_key == "thread-1"
    assert "Attachments: invoice.pdf" in text
    assert text.endswith("Please resend.")
    assert attachments[0]["visible_name"] == "invoice.pdf"
    record = AgentEmailMessage.objects.get(channel=channel)
    assert record.thread_key == "thread-1"
    assert record.provider_message_id == "msg1"

    chat = AgentChat.objects.create(
        agent=agent,
        source=AgentChat.Source.CHANNEL,
        channel=channel,
        channel_session_key="thread-1",
    )
    calls = []

    def send_request(method, url, headers, params=None, json=None):
        calls.append((method, url, params, json))
        if url.endswith("messages/send"):
            return 200, {"id": "sent-9"}
        return 200, {
            "payload": {"headers": [{"name": "Message-ID", "value": "<r1@gmail>"}]}
        }

    with token, patch(MAILBOX_REQUEST, side_effect=send_request):
        sent = channel_type.reply(channel, chat, "Attached again.")
    assert sent == {"to": "ann@customer.example", "subject": "Re: Invoice"}
    method, url, _, payload = calls[0]
    assert (method, url.split("/")[-2:]) == ("POST", ["messages", "send"])
    assert payload["threadId"] == "thread-1"
    import base64

    raw = base64.urlsafe_b64decode(payload["raw"]).decode()
    assert "In-Reply-To: <g1@mail.gmail.com>" in raw
    assert "References: <g1@mail.gmail.com>" in raw
    assert (
        AgentEmailMessage.objects.get(channel=channel, direction="outbound").message_id
        == "<r1@gmail>"
    )

    # The polling channel's own mail never triggers it.
    assert channel_type.own_addresses(channel) == {"help@company.example"}


@pytest.mark.django_db
def test_outlook_channel_polls_a_folder_with_delta_and_replies(
    email_setup, data_fixture
):
    user, application, agent = email_setup
    integration = data_fixture.create_microsoft_integration(
        application=application, account_email="help@contoso.example"
    )
    channel_type = OutlookAgentChatChannelType()
    config = channel_type.prepare_config(
        {
            "integration_id": integration.id,
            "folder": "inbox",
            "alias": "support@contoso.example",
        }
    )
    channel = AgentChatChannel.objects.create(
        application=application, type="outlook", name="Outlook", config=config
    )
    token = patch(
        "baserow_enterprise.agent_application.channels.mailbox"
        ".OAuth2IntegrationHandler.get_access_token",
        return_value="at",
    )

    # The first round walks the folder without reading it.
    first = [
        (200, {"value": [{"id": "old1"}], "@odata.nextLink": "https://graph/next"}),
        (
            200,
            {
                "value": [{"id": "old2"}],
                "@odata.deltaLink": "https://graph/delta?token=1",
            },
        ),
    ]
    with token, patch(MAILBOX_REQUEST, side_effect=first), patch(TASK) as delay:
        poll_mailbox_channels()
    delay.assert_not_called()
    channel.refresh_from_db()
    assert channel.config["cursor"] == "https://graph/delta?token=1"

    def fake_request(method, url, headers, params=None, json=None):
        if url == "https://graph/delta?token=1":
            return 200, {
                "value": [{"id": "new1"}, {"id": "gone", "@removed": {}}],
                "@odata.deltaLink": "https://graph/delta?token=2",
            }
        if url.endswith("/me/messages/new1"):
            return 200, {
                "id": "new1",
                "subject": "Quote request",
                "from": {
                    "emailAddress": {"name": "Bob", "address": "bob@customer.example"}
                },
                "toRecipients": [
                    {"emailAddress": {"address": "support@contoso.example"}}
                ],
                "internetMessageId": "<o1@outlook>",
                "conversationId": "conv-1",
                "body": {"contentType": "html", "content": "<p>How much for 10?</p>"},
                "hasAttachments": False,
                "internetMessageHeaders": [{"name": "In-Reply-To", "value": ""}],
            }
        raise AssertionError(f"unexpected request {url}")

    with token, patch(MAILBOX_REQUEST, side_effect=fake_request), patch(TASK) as delay:
        poll_mailbox_channels()
    channel.refresh_from_db()
    assert channel.config["cursor"] == "https://graph/delta?token=2"
    _, session_key, text, _, attachments, title = delay.call_args.args
    assert session_key == "conv-1"
    assert text.endswith("How much for 10?")
    assert attachments is None

    # Mail not addressed to the alias is left alone.
    def other_alias(method, url, headers, params=None, json=None):
        if url == "https://graph/delta?token=2":
            return 200, {
                "value": [{"id": "new2"}],
                "@odata.deltaLink": "https://graph/delta?token=3",
            }
        return 200, {
            "id": "new2",
            "subject": "Private",
            "from": {"emailAddress": {"address": "bob@customer.example"}},
            "toRecipients": [{"emailAddress": {"address": "help@contoso.example"}}],
            "internetMessageId": "<o2@outlook>",
            "conversationId": "conv-2",
            "body": {"contentType": "text", "content": "hi"},
        }

    with token, patch(MAILBOX_REQUEST, side_effect=other_alias), patch(TASK) as delay:
        poll_mailbox_channels()
    delay.assert_not_called()

    chat = AgentChat.objects.create(
        agent=agent,
        source=AgentChat.Source.CHANNEL,
        channel=channel,
        channel_session_key="conv-1",
    )
    with token, patch(MAILBOX_REQUEST, return_value=(202, None)) as request:
        sent = channel_type.reply(channel, chat, "About 100 euro.\nBest, Help")
    assert sent["to"] == "bob@customer.example"
    method, url = request.call_args.args[:2]
    assert (method, url) == (
        "POST",
        "https://graph.microsoft.com/v1.0/me/messages/new1/reply",
    )
    assert request.call_args.kwargs["json"] == {
        "comment": "About 100 euro.<br>Best, Help"
    }

    # The public config keeps the cursor to itself.
    public = channel_type.get_public_config(channel)
    assert "cursor" not in public and public["polling"] is True
