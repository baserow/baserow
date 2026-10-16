from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import close_old_connections

import pytest
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
)
from baserow.contrib.agent.exceptions import AgentConversationDoesNotExist
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentConversation, AgentMessage
from baserow.contrib.agent.service import AgentService
from baserow.core.action.models import Action

from .test_configuration import agent_url


def new_conversation(content="Hello\nworld"):
    return {"uuid": str(uuid4()), "message_uuid": str(uuid4()), "content": content}


def message_request(agent, view, conversation):
    if view == "conversations":
        return agent_url(agent, view), new_conversation()
    url = agent_url(agent, view, conversation_uuid=conversation.uuid)
    return url, {"uuid": str(uuid4()), "content": "Hello"}


@pytest.mark.django_db
def test_first_message_creates_a_private_conversation(
    configured_agent, api_client, api_user, mocker
):
    agent = configured_agent(user=api_user)
    registered = mocker.spy(
        CreateAgentConversationActionType, "send_action_done_signal"
    )
    payload = new_conversation("  Hello\nworld  ")

    response = api_client.post(agent_url(agent, "conversations"), payload)

    assert response.status_code == 200
    conversation = AgentConversation.objects.get()
    message = AgentMessage.objects.get()
    assert (conversation.owner_user, conversation.initiated_by) == (api_user, api_user)
    assert (conversation.title, conversation.visibility) == ("Hello world", "private")
    assert (message.author_user, message.content) == (api_user, payload["content"])
    assert response.json()["message"]["role"] == "user"
    assert registered.call_args.args[1] == {
        "agent_id": agent.id,
        "conversation_id": conversation.id,
        "message_id": message.id,
    }
    assert not Action.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "view,extra",
    [("conversations", {"visibility": "shared"}), ("messages", {"role": "system"})],
)
def test_clients_cannot_set_conversation_or_message_metadata(
    data_fixture, configured_agent, api_client, api_user, view, extra
):
    agent = configured_agent(user=api_user)
    conversation = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    url, payload = message_request(agent, view, conversation)

    response = api_client.post(url, {**payload, **extra})

    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert not AgentMessage.objects.exists()


@pytest.mark.django_db
def test_failed_first_message_leaves_no_conversation_or_action(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    registered = mocker.spy(
        CreateAgentConversationActionType, "send_action_done_signal"
    )
    mocker.patch.object(AgentHandler, "create_message", side_effect=RuntimeError)

    with pytest.raises(RuntimeError):
        CreateAgentConversationActionType.do(user, agent.id, uuid4(), uuid4(), "Hi")

    assert not AgentConversation.objects.exists()
    registered.assert_not_called()


@pytest.mark.django_db
def test_retries_return_the_accepted_message_and_conflicts_are_rejected(
    configured_agent, api_client, api_user, mocker
):
    created = mocker.spy(CreateAgentConversationActionType, "send_action_done_signal")
    appended = mocker.spy(CreateAgentMessageActionType, "send_action_done_signal")
    agent = configured_agent(user=api_user)
    payload = new_conversation()
    url = agent_url(agent, "conversations")
    first = api_client.post(url, payload)
    messages_url = agent_url(agent, "messages", conversation_uuid=payload["uuid"])
    append = {"uuid": str(uuid4()), "content": "Next"}
    second = api_client.post(messages_url, append)
    agent.instructions = ""
    agent.save()

    for target, body, accepted in [
        (url, payload, first),
        (messages_url, append, second),
    ]:
        retried = api_client.post(target, body)
        assert retried.json()["message"] == accepted.json()["message"]
    for target, body in [
        (url, {**payload, "content": "Different"}),
        (url, {**payload, "message_uuid": str(uuid4())}),
        (messages_url, {**append, "content": "Different"}),
    ]:
        response = api_client.post(target, body)
        assert response.status_code == 409
        assert response.json()["error"] == "ERROR_AGENT_MESSAGE_CONFLICT"
    assert AgentMessage.objects.count() == 2
    created.assert_called_once()
    appended.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["other owner", "shared visibility", "other agent"])
def test_conversations_are_private_to_their_owner_and_agent(
    data_fixture, configured_agent, case
):
    owner = data_fixture.create_user()
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner, members=[other])
    agent = configured_agent(workspace=workspace)
    conversation = data_fixture.create_agent_conversation(
        user=owner,
        agent=agent,
        visibility="shared" if case == "shared visibility" else "private",
    )
    message = data_fixture.create_agent_message(user=owner, conversation=conversation)
    actor, target = (
        (owner, configured_agent(workspace=workspace))
        if case == "other agent"
        else (other, agent)
    )
    service = AgentService()

    assert not service.list_conversations(actor, target.id).exists()
    for attempt in [
        lambda: service.list_messages(actor, target.id, conversation.uuid),
        lambda: service.create_message(
            actor, target.id, conversation.uuid, uuid4(), "Hello"
        ),
        lambda: service.create_conversation(
            actor, target.id, conversation.uuid, message.uuid, message.content
        ),
    ]:
        with pytest.raises(AgentConversationDoesNotExist):
            attempt()
    assert AgentMessage.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["conversations", "messages"])
def test_new_messages_require_a_ready_configuration(
    data_fixture, configured_agent, api_client, api_user, view
):
    agent = configured_agent(
        user=api_user, instructions="PRIVATE", model_identifier="x"
    )
    conversation = data_fixture.create_agent_conversation(user=api_user, agent=agent)

    response = api_client.post(*message_request(agent, view, conversation))

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_AGENT_CONFIGURATION_INVALID"
    assert "PRIVATE" not in response.content.decode()
    assert not AgentMessage.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("content", [" \n\t", "x" * 100001])
def test_message_content_must_be_present_and_bounded(
    data_fixture, configured_agent, content
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    service = AgentService()

    with pytest.raises(ValidationError):
        service.create_conversation(user, agent.id, uuid4(), uuid4(), content)
    with pytest.raises(ValidationError):
        service.create_message(user, agent.id, conversation.uuid, uuid4(), content)

    assert AgentConversation.objects.count() == 1
    assert not AgentMessage.objects.exists()


@pytest.mark.django_db
def test_history_is_paginated_newest_first_with_chronological_message_pages(
    data_fixture, configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    for index in range(3):
        with freeze_time(f"2026-10-14 08:0{index}:00"):
            conversation = data_fixture.create_agent_conversation(
                user=api_user, agent=agent, title=str(index)
            )
    for index in range(5):
        data_fixture.create_agent_message(
            user=api_user, conversation=conversation, content=str(index)
        )
    messages_url = agent_url(agent, "messages", conversation_uuid=conversation.uuid)

    conversations = api_client.get(agent_url(agent, "conversations") + "?size=2")
    pages = [
        api_client.get(messages_url + f"?size=2&page={page}").json() for page in (1, 2)
    ]

    assert [item["title"] for item in conversations.json()["results"]] == ["2", "1"]
    assert [[item["content"] for item in page["results"]] for page in pages] == [
        ["3", "4"],
        ["1", "2"],
    ]
    assert api_client.get(messages_url + "?size=101").status_code == 400


@pytest.mark.django_db(transaction=True)
def test_concurrent_creation_with_one_uuid_in_two_agents_creates_one_conversation(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    first = configured_agent(user=user)
    second = configured_agent(workspace=first.workspace)
    uuid, message_uuid = uuid4(), uuid4()
    barrier = Barrier(2)
    original = AgentHandler.get_creation_retry

    def both_observe_unused_uuid(handler, *args):
        result = original(handler, *args)
        if result is None:
            barrier.wait(timeout=10)
        return result

    mocker.patch.object(AgentHandler, "get_creation_retry", both_observe_unused_uuid)

    def create(agent_id):
        close_old_connections()
        try:
            actor = get_user_model().objects.get(id=user.id)
            CreateAgentConversationActionType.do(
                actor, agent_id, uuid, message_uuid, "Hello"
            )
            return "created"
        except AgentConversationDoesNotExist:
            return "missing"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, [first.id, second.id]))

    assert sorted(results) == ["created", "missing"]
    assert AgentConversation.objects.count() == AgentMessage.objects.count() == 1


@pytest.mark.django_db
def test_deleting_a_user_removes_their_conversations_and_their_attribution(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    participant = data_fixture.create_user()
    agent = configured_agent(
        workspace=data_fixture.create_workspace(user=owner, members=[participant])
    )
    data_fixture.create_agent_conversation(user=participant, agent=agent)
    retained = data_fixture.create_agent_conversation(
        user=owner, agent=agent, initiated_by=participant
    )
    message = data_fixture.create_agent_message(user=participant, conversation=retained)

    participant.delete()

    assert list(AgentConversation.objects.all()) == [retained]
    retained.refresh_from_db()
    message.refresh_from_db()
    assert (retained.initiated_by_id, message.author_user_id) == (None, None)
