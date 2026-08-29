import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.channels.registries import (
    start_channel_chat,
)
from baserow_enterprise.agent_application.channels.slack import (
    SlackAgentChatChannelType,
)
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatChannel,
    AgentChatMessage,
)

from .test_agent_runner import register_runner_test_model_type

SIGNING_SECRET = "test-signing-secret"
BOT_TOKEN = "xoxb-test-token"


@pytest.fixture
def channel_setup(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    application.active = True
    application.save(update_fields=["active"])
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="test-model",
    )
    channel = AgentChatChannel.objects.create(
        application=application,
        type="slack",
        name="Slack",
        config={"bot_token": BOT_TOKEN, "signing_secret": SIGNING_SECRET},
    )
    return user, application, agent, channel


def _slack_event_body(event, event_id="Ev123"):
    return json.dumps(
        {"type": "event_callback", "event_id": event_id, "event": event}
    ).encode()


def _sign(body: bytes, secret: str = SIGNING_SECRET, timestamp: str | None = None):
    timestamp = timestamp or str(int(time.time()))
    basestring = b"v0:" + timestamp.encode() + b":" + body
    signature = (
        "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    )
    return timestamp, signature


def _post_event(api_client, channel, body: bytes, secret=SIGNING_SECRET, **overrides):
    timestamp, signature = _sign(body, secret)
    headers = {
        "HTTP_X_SLACK_REQUEST_TIMESTAMP": overrides.get("timestamp", timestamp),
        "HTTP_X_SLACK_SIGNATURE": overrides.get("signature", signature),
    }
    return api_client.post(
        f"/api/agent_application/channels/{channel.uid}/events/",
        data=body,
        content_type="application/json",
        **headers,
    )


@pytest.mark.django_db
def test_url_verification_challenge(api_client, channel_setup):
    user, application, agent, channel = channel_setup
    body = json.dumps({"type": "url_verification", "challenge": "abc123"}).encode()

    response = _post_event(api_client, channel, body)

    assert response.status_code == 200
    assert response.json() == {"challenge": "abc123"}


@pytest.mark.django_db
def test_invalid_signature_is_rejected(api_client, channel_setup):
    user, application, agent, channel = channel_setup
    body = _slack_event_body({"type": "message", "user": "U1", "text": "hi"})

    response = _post_event(api_client, channel, body, secret="wrong-secret")
    assert response.status_code == 401

    # A stale timestamp is also rejected (replay protection).
    stale = str(int(time.time()) - 3600)
    _, signature = _sign(body, SIGNING_SECRET, stale)
    response = _post_event(
        api_client, channel, body, timestamp=stale, signature=signature
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_direct_message_event_enqueues_processing(api_client, channel_setup):
    user, application, agent, channel = channel_setup
    body = _slack_event_body(
        {
            "type": "message",
            "channel_type": "im",
            "channel": "D123",
            "user": "U1",
            "text": "Hello agent",
        }
    )

    with patch(
        "baserow_enterprise.agent_application.tasks.process_agent_channel_message.delay"
    ) as delay_mock:
        response = _post_event(api_client, channel, body)

    assert response.status_code == 200
    delay_mock.assert_called_once_with(channel.id, "D123|", "Hello agent", "")


@pytest.mark.django_db
def test_app_mention_event_threads_and_strips_mention(api_client, channel_setup):
    user, application, agent, channel = channel_setup
    body = _slack_event_body(
        {
            "type": "app_mention",
            "channel": "C42",
            "user": "U1",
            "text": "<@UBOT> please help",
            "ts": "111.222",
        }
    )

    with patch(
        "baserow_enterprise.agent_application.tasks.process_agent_channel_message.delay"
    ) as delay_mock:
        response = _post_event(api_client, channel, body)

    assert response.status_code == 200
    delay_mock.assert_called_once_with(
        channel.id, "C42|111.222", "please help", "<@U1>"
    )


@pytest.mark.django_db
def test_bot_and_channel_messages_are_ignored(api_client, channel_setup):
    user, application, agent, channel = channel_setup

    events = [
        # The bot's own messages must never trigger the agent.
        {"type": "message", "channel_type": "im", "bot_id": "B1", "text": "hi"},
        # Message edits/deletes have a subtype.
        {
            "type": "message",
            "channel_type": "im",
            "user": "U1",
            "subtype": "message_changed",
            "text": "hi",
        },
        # Plain channel messages only reach the agent as mentions.
        {"type": "message", "channel_type": "channel", "user": "U1", "text": "hi"},
    ]

    with patch(
        "baserow_enterprise.agent_application.tasks.process_agent_channel_message.delay"
    ) as delay_mock:
        for index, event in enumerate(events):
            response = _post_event(
                api_client, channel, _slack_event_body(event, event_id=f"Ev{index}")
            )
            assert response.status_code == 200

    delay_mock.assert_not_called()


@pytest.mark.django_db
def test_duplicate_event_deliveries_are_deduplicated(api_client, channel_setup):
    user, application, agent, channel = channel_setup
    body = _slack_event_body(
        {
            "type": "message",
            "channel_type": "im",
            "channel": "D123",
            "user": "U1",
            "text": "Hello",
        },
        event_id="EvDup",
    )

    with patch(
        "baserow_enterprise.agent_application.tasks.process_agent_channel_message.delay"
    ) as delay_mock:
        _post_event(api_client, channel, body)
        _post_event(api_client, channel, body)

    assert delay_mock.call_count == 1


@pytest.mark.django_db
def test_unknown_channel_uid_returns_no_content(api_client, channel_setup):
    import uuid

    response = api_client.post(
        f"/api/agent_application/channels/{uuid.uuid4()}/events/",
        data=b"{}",
        content_type="application/json",
    )
    assert response.status_code == 204


@pytest.mark.django_db(transaction=True)
def test_start_channel_chat_creates_chat_and_reuses_session(channel_setup):
    user, application, agent, channel = channel_setup

    with patch(
        "baserow_enterprise.agent_application.handler.AgentChatHandler.start_chat_run"
    ) as start_mock:
        message = start_channel_chat(channel, "D123|", "Hello", "")

    assert message is not None
    chat = AgentChat.objects.get(channel=channel, channel_session_key="D123|")
    assert chat.source == AgentChat.Source.CHANNEL
    assert chat.user_id is None
    assert chat.messages.get().content == "Hello"
    start_mock.assert_called_once()

    # A second message in the same Slack conversation continues the chat.
    with patch(
        "baserow_enterprise.agent_application.handler.AgentChatHandler.start_chat_run"
    ):
        start_channel_chat(channel, "D123|", "Again", "")

    assert AgentChat.objects.filter(channel=channel).count() == 1
    assert chat.messages.count() == 2


@pytest.mark.django_db
def test_start_channel_chat_requires_active_application_and_enabled_channel(
    channel_setup,
):
    user, application, agent, channel = channel_setup

    application.active = False
    application.save(update_fields=["active"])
    assert start_channel_chat(channel, "D123|", "Hello") is None

    application.active = True
    application.save(update_fields=["active"])
    channel.enabled = False
    channel.save(update_fields=["enabled"])
    assert start_channel_chat(channel, "D123|", "Hello") is None
    assert AgentChat.objects.filter(channel=channel).count() == 0


@pytest.mark.django_db
def test_send_response_posts_to_slack_thread(channel_setup):
    user, application, agent, channel = channel_setup
    chat = AgentChat.objects.create(
        agent=agent,
        source=AgentChat.Source.CHANNEL,
        channel=channel,
        channel_session_key="C42|111.222",
    )

    request_mock = MagicMock()
    request_mock.return_value.json.return_value = {"ok": True}
    with patch(
        "baserow_enterprise.agent_application.channels.slack.get_http_request_function",
        return_value=request_mock,
    ):
        SlackAgentChatChannelType().send_response(channel, chat, "The answer")

    kwargs = request_mock.call_args.kwargs
    assert kwargs["url"] == "https://slack.com/api/chat.postMessage"
    assert kwargs["headers"]["Authorization"] == f"Bearer {BOT_TOKEN}"
    assert kwargs["params"]["channel"] == "C42"
    assert kwargs["params"]["thread_ts"] == "111.222"
    assert kwargs["params"]["text"] == "The answer"


@pytest.mark.django_db(transaction=True)
def test_channel_chat_run_posts_answer_back(channel_setup):
    from baserow_enterprise.agent_application.tasks import (
        process_agent_channel_message,
    )

    user, application, agent, channel = channel_setup

    request_mock = MagicMock()
    request_mock.return_value.json.return_value = {"ok": True}
    with (
        patch(
            "baserow_enterprise.agent_application.channels.slack"
            ".get_http_request_function",
            return_value=request_mock,
        ),
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        process_agent_channel_message(channel.id, "D123|", "Hello agent", "")

    chat = AgentChat.objects.get(channel=channel)
    assert chat.status == AgentChat.Status.IDLE
    ai_message = chat.messages.filter(role=AgentChatMessage.Role.AI).last()
    assert ai_message.content
    # The final answer was posted back into the Slack conversation.
    assert request_mock.call_args.kwargs["params"]["text"] == ai_message.content


@pytest.mark.django_db
def test_channel_api_crud_masks_secrets(api_client, data_fixture, channel_setup):
    user, application, agent, channel = channel_setup
    token = data_fixture.generate_token(user)

    response = api_client.get(
        f"/api/agent_application/{application.id}/channels/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    listed = response.json()
    assert len(listed) == 1
    assert listed[0]["config"] == {"bot_token_set": True, "signing_secret_set": True}
    assert BOT_TOKEN not in json.dumps(listed)
    assert str(channel.uid) in listed[0]["events_url"]

    response = api_client.post(
        f"/api/agent_application/{application.id}/channels/",
        {
            "type": "slack",
            "name": "Second",
            "config": {"bot_token": "xoxb-2", "signing_secret": "sec-2"},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    channel_id = response.json()["id"]

    # Updating without secrets keeps the stored ones.
    response = api_client.patch(
        f"/api/agent_application/channels/{channel_id}/",
        {"name": "Renamed", "config": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    updated = AgentChatChannel.objects.get(id=channel_id)
    assert updated.name == "Renamed"
    assert updated.config["bot_token"] == "xoxb-2"

    response = api_client.delete(
        f"/api/agent_application/channels/{channel_id}/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204
    assert not AgentChatChannel.objects.filter(id=channel_id).exists()


@pytest.mark.django_db
def test_create_channel_without_credentials_fails(
    api_client, data_fixture, channel_setup
):
    user, application, agent, channel = channel_setup
    token = data_fixture.generate_token(user)

    response = api_client.post(
        f"/api/agent_application/{application.id}/channels/",
        {"type": "slack", "config": {"bot_token": "xoxb-3"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_channels_survive_duplicate_but_not_snapshot(channel_setup):
    from baserow.core.registries import ImportExportConfig, application_type_registry

    user, application, agent, channel = channel_setup
    application_type = application_type_registry.get("agent")

    duplicate_config = ImportExportConfig(
        include_permission_data=True, reduce_disk_space_usage=False, is_duplicate=True
    )
    serialized = application_type.export_serialized(application, duplicate_config)
    assert len(serialized["chat_channels"]) == 1
    assert serialized["chat_channels"][0]["config"]["bot_token"] == BOT_TOKEN

    snapshot_config = ImportExportConfig(
        include_permission_data=True, reduce_disk_space_usage=False
    )
    serialized_snapshot = application_type.export_serialized(
        application, snapshot_config
    )
    assert serialized_snapshot["chat_channels"] == []

    imported = application_type.import_serialized(
        application.workspace,
        serialized,
        duplicate_config,
        {},
    )
    imported_channel = AgentChatChannel.objects.get(application=imported)
    assert imported_channel.config["bot_token"] == BOT_TOKEN
    # The copy gets its own webhook URL.
    assert imported_channel.uid != channel.uid
