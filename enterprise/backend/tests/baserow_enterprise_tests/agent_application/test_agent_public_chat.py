from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
)

from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.channels.web import (
    WebAgentChatChannelType,
    public_chat_status,
)
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatChannel,
    AgentChatMessage,
)
from baserow_enterprise.agent_application.realtime import public_chat_event
from baserow_enterprise.agent_application.runner import AgentRunner
from baserow_enterprise.agent_application.ws.pages import PublicAgentChatPageType

from .test_agent_runner import register_runner_test_model_type


@pytest.fixture
def web_channel(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Docs")
        .specific
    )
    application.active = True
    application.save(update_fields=["active"])
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent, ai_generative_ai_type="agent_runner_test", ai_generative_ai_model="m"
    )
    channel_type = WebAgentChatChannelType()
    channel = AgentChatChannel.objects.create(
        application=application,
        type=channel_type.type,
        name="Help",
        config=channel_type.prepare_config(
            {"title": "Ask the docs", "welcome_text": "Hi there"}
        ),
    )
    return user, application, agent, channel


def _header(token):
    return {
        f"HTTP_{settings.PUBLIC_AGENT_CHAT_AUTHORIZATION_HEADER.upper().replace('-', '_')}": f"JWT {token}"
    }


def _url(channel, suffix=""):
    return f"/api/agent_application/public/chat/{channel.config['slug']}/{suffix}"


# --------------------------------------------------------------------------
# Channel type
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_web_channel_config_slug_password_and_token(web_channel):
    user, application, agent, channel = web_channel
    channel_type = WebAgentChatChannelType()
    assert channel.config["slug"]
    assert channel_type.has_password(channel) is False
    assert channel_type.get_public_config(channel) == {
        "slug": channel.config["slug"],
        "has_password": False,
        "title": "Ask the docs",
        "welcome_text": "Hi there",
    }

    channel.config = channel_type.prepare_config(
        {"password": "secret"}, existing_config=channel.config
    )
    assert channel_type.has_password(channel)
    assert channel.config["password"] != "secret"
    assert channel_type.check_password(channel, "secret")
    assert not channel_type.check_password(channel, "nope")
    token = channel_type.encode_token(channel)
    assert channel_type.is_token_valid(channel, token)
    assert not channel_type.is_token_valid(channel, token + "x")

    # Rotating the link invalidates tokens; clearing the password too.
    old_slug = channel.config["slug"]
    channel_type.rotate_slug(channel)
    assert channel.config["slug"] != old_slug
    assert not channel_type.is_token_valid(channel, token)
    channel.config = channel_type.prepare_config(
        {"password": ""}, existing_config=channel.config
    )
    assert channel_type.has_password(channel) is False


def test_public_chat_event_filter_only_passes_answers():
    assert public_chat_event({"type": "tool_call", "tool_name": "x"}) is None
    assert public_chat_event({"type": "ai/reasoning", "content": "secret"}) is None
    assert public_chat_event({"type": "approval_request", "approvals": []}) is None
    assert public_chat_event({"type": "ai/thinking", "content": "Using x"}) is None
    assert public_chat_event(
        {"type": "ai/message", "id": 4, "content": "Hi", "sources": ["u"]}
    ) == {"type": "ai/message", "id": 4, "content": "Hi"}
    assert public_chat_event({"type": "ai/error", "content": "boom", "code": "x"}) == {
        "type": "ai/error"
    }
    assert public_chat_event({"type": "ai/answer_chunk", "content": "H"}) == {
        "type": "ai/answer_chunk",
        "content": "H",
    }
    assert public_chat_status(AgentChat.Status.AWAITING_APPROVAL) == (
        "waiting_for_approval"
    )
    assert public_chat_status(AgentChat.Status.CANCELING) == "working"


@pytest.mark.django_db
def test_web_channel_runs_without_the_memory_tool(web_channel):
    user, application, agent, channel = web_channel
    chat = AgentChatHandler().create_public_chat(channel)
    runner = AgentRunner.__new__(AgentRunner)
    runner.agent = agent
    runner.chat = chat
    runner.deps = SimpleNamespace(system_notes=[], skills=[])
    with (
        patch(
            "baserow_enterprise.agent_application.tools.registries."
            "agent_tool_type_registry.build_toolsets",
            return_value=[],
        ),
        patch(
            "baserow_enterprise.agent_application.tools.memory.build_memory_toolset"
        ) as memory,
    ):
        toolsets = runner._build_toolsets()
    assert toolsets == []
    memory.assert_not_called()
    assert any("anonymous visitor" in note for note in runner.deps.system_notes)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_public_chat_info_and_password(api_client, web_channel):
    user, application, agent, channel = web_channel
    response = api_client.get(_url(channel))
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "title": "Ask the docs",
        "welcome_text": "Hi there",
        "agent_name": agent.name,
        "has_password": False,
    }
    assert api_client.get("/api/agent_application/public/chat/nope/").status_code == (
        HTTP_404_NOT_FOUND
    )

    channel_type = WebAgentChatChannelType()
    channel.config = channel_type.prepare_config(
        {"password": "secret"}, existing_config=channel.config
    )
    channel.save()
    assert api_client.get(_url(channel)).status_code == HTTP_401_UNAUTHORIZED
    bad = api_client.post(_url(channel, "auth/"), {"password": "x"}, format="json")
    assert bad.status_code == HTTP_401_UNAUTHORIZED
    ok = api_client.post(_url(channel, "auth/"), {"password": "secret"}, format="json")
    assert ok.status_code == HTTP_200_OK
    token = ok.json()["access_token"]
    assert api_client.get(_url(channel), **_header(token)).status_code == HTTP_200_OK

    # A disabled channel or inactive agent hides the link entirely.
    channel.enabled = False
    channel.save()
    assert api_client.get(_url(channel), **_header(token)).status_code == (
        HTTP_404_NOT_FOUND
    )


@pytest.mark.django_db
def test_public_chat_conversation_flow_and_transcript_filtering(
    api_client, web_channel
):
    user, application, agent, channel = web_channel
    created = api_client.post(_url(channel, "conversations/"))
    assert created.status_code == HTTP_201_CREATED
    uuid = created.json()["uuid"]
    assert created.json()["status"] == "idle"
    chat = AgentChat.objects.get(uuid=uuid)
    assert chat.source == AgentChat.Source.CHANNEL
    assert chat.channel_id == channel.id

    with patch("baserow_enterprise.agent_application.tasks.run_agent_chat.delay"):
        sent = api_client.post(
            _url(channel, f"conversations/{uuid}/messages/"),
            {"content": "Hello?"},
            format="json",
        )
    assert sent.status_code == HTTP_202_ACCEPTED
    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.IN_PROGRESS
    busy = api_client.post(
        _url(channel, f"conversations/{uuid}/messages/"),
        {"content": "Again"},
        format="json",
    )
    assert busy.status_code == HTTP_400_BAD_REQUEST
    assert busy.json()["error"] == "ERROR_AGENT_CHAT_ALREADY_RUNNING"

    # Internal details never reach the transcript.
    AgentChatHandler().create_message(chat, AgentChatMessage.Role.SYSTEM, "Trigger")
    answer = AgentChatMessage.objects.create(
        chat=chat,
        role=AgentChatMessage.Role.AI,
        content="The answer",
        artifacts={"events": [{"type": "tool_call", "tool_name": "list_rows"}]},
    )
    AgentChatMessage.objects.create(
        chat=chat, role=AgentChatMessage.Role.AI, content="", artifacts={"cancelled": 1}
    )
    chat.status = AgentChat.Status.AWAITING_APPROVAL
    chat.save()
    transcript = api_client.get(_url(channel, f"conversations/{uuid}/")).json()
    assert transcript["status"] == "waiting_for_approval"
    assert [(m["role"], m["content"]) for m in transcript["messages"]] == [
        ("human", "Hello?"),
        ("ai", "The answer"),
    ]
    assert set(transcript["messages"][1].keys()) == {
        "id",
        "role",
        "content",
        "created_on",
    }
    assert transcript["messages"][1]["id"] == answer.id
    assert "artifacts" not in str(transcript)

    assert api_client.get(
        _url(channel, "conversations/does-not-exist/")
    ).status_code == (HTTP_404_NOT_FOUND)


@pytest.mark.django_db
def test_public_chat_message_limits(api_client, web_channel):
    user, application, agent, channel = web_channel
    uuid = api_client.post(_url(channel, "conversations/")).json()["uuid"]
    chat = AgentChat.objects.get(uuid=uuid)
    AgentChatHandler().create_message(chat, AgentChatMessage.Role.HUMAN, "one")

    with override_settings(AGENT_PUBLIC_CHAT_MAX_MESSAGES=1):
        response = api_client.post(
            _url(channel, f"conversations/{uuid}/messages/"),
            {"content": "two"},
            format="json",
        )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PUBLIC_CHAT_MESSAGE_LIMIT_REACHED"

    with override_settings(AGENT_APPLICATION_CHANNEL_RATE_LIMIT_PER_MINUTE=0):
        response = api_client.post(
            _url(channel, f"conversations/{uuid}/messages/"),
            {"content": "two"},
            format="json",
        )
    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_public_chat_ws_page_requires_the_token_and_a_known_conversation(
    web_channel,
):
    user, application, agent, channel = web_channel
    chat = AgentChatHandler().create_public_chat(channel)
    page = PublicAgentChatPageType()
    slug = channel.config["slug"]
    assert page.can_add(None, "ws", slug=slug, token=None, conversation=str(chat.uuid))
    assert not page.can_add(None, "ws", slug=slug, token=None, conversation="other")
    assert not page.can_add(
        None, "ws", slug="x", token=None, conversation=str(chat.uuid)
    )

    channel_type = WebAgentChatChannelType()
    channel.config = channel_type.prepare_config(
        {"password": "pw"}, existing_config=channel.config
    )
    channel.save()
    assert not page.can_add(
        None, "ws", slug=slug, token=None, conversation=str(chat.uuid)
    )
    token = channel_type.encode_token(channel)
    assert page.can_add(None, "ws", slug=slug, token=token, conversation=str(chat.uuid))
    assert page.get_group_name(conversation=str(chat.uuid)) == (
        f"public-agent-chat-{chat.uuid}"
    )
