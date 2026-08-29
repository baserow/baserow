from unittest.mock import patch
from uuid import uuid4

from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
)

from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import AgentChat, AgentChatMessage


@pytest.fixture
def agent_setup(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
    )
    return user, token, application, agent


@pytest.mark.django_db(transaction=True)
def test_send_message_creates_chat_and_enqueues_run(api_client, agent_setup):
    user, token, application, agent = agent_setup
    chat_uuid = uuid4()

    url = reverse(
        "api:agent:chat_messages",
        kwargs={"application_id": application.id, "chat_uuid": chat_uuid},
    )
    with (
        patch(
            "baserow_enterprise.agent_application.tasks.run_agent_chat.delay"
        ) as delay_mock,
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        response = api_client.post(
            url,
            {"content": "Hello agent"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_202_ACCEPTED
    chat = AgentChat.objects.get(uuid=chat_uuid)
    assert chat.agent_id == agent.id
    assert chat.user_id == user.id
    assert chat.status == AgentChat.Status.IN_PROGRESS
    assert chat.messages.filter(role=AgentChatMessage.Role.HUMAN).count() == 1
    delay_mock.assert_called_once()


@pytest.mark.django_db
def test_send_message_requires_configured_model(api_client, agent_setup):
    user, token, application, agent = agent_setup
    AgentApplicationHandler().update_agent(agent, ai_generative_ai_type=None)

    url = reverse(
        "api:agent:chat_messages",
        kwargs={"application_id": application.id, "chat_uuid": uuid4()},
    )
    response = api_client.post(
        url, {"content": "Hi"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AGENT_MODEL_NOT_CONFIGURED"


@pytest.mark.django_db
def test_send_message_rejected_while_running(api_client, agent_setup):
    user, token, application, agent = agent_setup
    chat = AgentChat.objects.create(
        agent=agent, user=user, status=AgentChat.Status.IN_PROGRESS
    )

    url = reverse(
        "api:agent:chat_messages",
        kwargs={"application_id": application.id, "chat_uuid": chat.uuid},
    )
    response = api_client.post(
        url, {"content": "Hi"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AGENT_CHAT_ALREADY_RUNNING"


@pytest.mark.django_db
def test_list_chats_and_messages(api_client, agent_setup):
    user, token, application, agent = agent_setup
    chat = AgentChat.objects.create(agent=agent, user=user, title="First")
    AgentChatHandler().create_message(chat, AgentChatMessage.Role.HUMAN, "Hi")
    AgentChatHandler().create_message(chat, AgentChatMessage.Role.AI, "Hello!")

    url = reverse("api:agent:chats", kwargs={"application_id": application.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["count"] == 1
    assert [c["title"] for c in data["results"]] == ["First"]

    url = reverse(
        "api:agent:chat_messages",
        kwargs={"application_id": application.id, "chat_uuid": chat.uuid},
    )
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["chat"]["id"] == chat.id
    assert [m["content"] for m in data["messages"]] == ["Hi", "Hello!"]


@pytest.mark.django_db
def test_cancel_and_delete_chat(api_client, agent_setup):
    user, token, application, agent = agent_setup
    chat = AgentChat.objects.create(
        agent=agent, user=user, status=AgentChat.Status.IN_PROGRESS
    )

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        url = reverse("api:agent:chat_cancel", kwargs={"chat_uuid": chat.uuid})
        response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_204_NO_CONTENT
    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.CANCELING

    # A running (canceling) chat cannot be deleted.
    url = reverse("api:agent:chat_item", kwargs={"chat_uuid": chat.uuid})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST

    chat.status = AgentChat.Status.IDLE
    chat.save()
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT
    assert not AgentChat.objects.filter(id=chat.id).exists()


@pytest.mark.django_db
def test_agent_usage_endpoint(api_client, agent_setup):
    user, token, application, agent = agent_setup
    AgentChat.objects.create(
        agent=agent, user=user, total_input_tokens=100, total_output_tokens=20
    )
    AgentChat.objects.create(agent=agent, total_input_tokens=50, total_output_tokens=5)

    url = reverse("api:agent:usage", kwargs={"application_id": application.id})
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "total_input_tokens": 150,
        "total_output_tokens": 25,
        "chat_count": 2,
    }


@pytest.mark.django_db
def test_clean_up_old_agent_chats(agent_setup):
    from datetime import timedelta

    from django.utils import timezone

    from baserow_enterprise.agent_application.tasks import clean_up_old_agent_chats

    user, token, application, agent = agent_setup
    old = timezone.now() - timedelta(days=60)

    old_triggered = AgentChat.objects.create(
        agent=agent, source=AgentChat.Source.TRIGGER
    )
    AgentChat.objects.filter(id=old_triggered.id).update(updated_on=old)
    old_manual = AgentChat.objects.create(
        agent=agent, user=user, source=AgentChat.Source.MANUAL
    )
    AgentChat.objects.filter(id=old_manual.id).update(updated_on=old)
    running_old = AgentChat.objects.create(
        agent=agent,
        source=AgentChat.Source.TRIGGER,
        status=AgentChat.Status.IN_PROGRESS,
    )
    AgentChat.objects.filter(id=running_old.id).update(updated_on=old)
    recent_triggered = AgentChat.objects.create(
        agent=agent, source=AgentChat.Source.TRIGGER
    )

    clean_up_old_agent_chats()

    remaining = set(AgentChat.objects.values_list("id", flat=True))
    assert old_triggered.id not in remaining
    assert {old_manual.id, running_old.id, recent_triggered.id} <= remaining


@pytest.mark.django_db
def test_clean_up_recovers_stuck_running_chats(agent_setup):
    from datetime import timedelta

    from django.utils import timezone

    from baserow_enterprise.agent_application.tasks import clean_up_old_agent_chats

    user, token, application, agent = agent_setup
    stale = timezone.now() - timedelta(hours=1)

    stuck = AgentChat.objects.create(
        agent=agent, user=user, status=AgentChat.Status.IN_PROGRESS
    )
    AgentChat.objects.filter(id=stuck.id).update(updated_on=stale)
    active = AgentChat.objects.create(
        agent=agent, user=user, status=AgentChat.Status.IN_PROGRESS
    )

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        clean_up_old_agent_chats()

    stuck.refresh_from_db()
    active.refresh_from_db()
    assert stuck.status == AgentChat.Status.ERROR
    assert stuck.completed_on is not None
    assert active.status == AgentChat.Status.IN_PROGRESS


@pytest.mark.django_db
def test_message_and_delete_broadcasts_for_collaborators(agent_setup):
    user, token, application, agent = agent_setup
    chat = AgentChat.objects.create(agent=agent, user=user)

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ) as broadcast_mock:
        message = AgentChatHandler().create_message(
            chat, AgentChatMessage.Role.HUMAN, "Hello there"
        )
        chat_id = chat.id
        AgentChatHandler().delete_chat(chat)

    payloads = [args[0][1] for args in broadcast_mock.delay.call_args_list]
    message_events = [p["event"] for p in payloads if p["type"] == "agent_chat_event"]
    assert {
        "type": "human",
        "id": message.id,
        "content": "Hello there",
        "attachments": [],
    } in message_events
    assert {"type": "agent_chat_deleted", "chat_id": chat_id} in payloads
