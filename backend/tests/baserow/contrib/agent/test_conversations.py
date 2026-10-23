from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import ANY
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, transaction

import pytest
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
)
from baserow.contrib.agent.exceptions import (
    AgentConversationDoesNotExist,
    AgentMessageConflict,
    AgentNotReady,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentConversation, AgentMessage
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.signals import agent_conversation_updated
from baserow.core.action.models import Action
from baserow.core.chat_runs.models import ChatRun

from .utils import agent_url, new_conversation, run_reply


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
    payload = new_conversation("  Hello\nworld  " + "x" * 300)

    response = api_client.post(agent_url(agent, "conversations"), payload)
    conversation = AgentConversation.objects.get()
    message = AgentMessage.objects.get()

    assert response.json() == {
        "conversation": {
            "id": AgentConversation.objects.get().id,
            "uuid": payload["uuid"],
            "title": "Hello world " + "x" * 238,
            "created_on": ANY,
            "updated_on": ANY,
        },
        "message": {
            "id": message.id,
            "uuid": payload["message_uuid"],
            "role": "user",
            "content": payload["content"],
            "created_on": ANY,
            "turn": {
                "id": AgentMessage.objects.get().turn_id,
                "status": "running",
                "error_code": "",
                "run_id": ANY,
            },
        },
    }
    assert conversation.owner_user == api_user
    assert registered.call_args.args[1] == {
        "agent_id": agent.id,
        "conversation_id": conversation.id,
        "message_id": message.id,
    }
    assert not Action.objects.exists()


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
    run_reply(ChatRun.objects.get())
    messages_url = agent_url(agent, "messages", conversation_uuid=payload["uuid"])
    append = {"uuid": str(uuid4()), "content": "Next"}
    second = api_client.post(messages_url, append)
    # Accepted retries and conflicts must not depend on the current readiness.
    agent.instructions = ""
    agent.save()

    for target, body, accepted, status, run_id in [
        (url, payload, first, "completed", None),
        (
            messages_url,
            append,
            second,
            "running",
            second.json()["message"]["turn"]["run_id"],
        ),
    ]:
        retried = api_client.post(target, body)
        message = accepted.json()["message"]
        # The turn is live state: the reply finished since the first response.
        assert retried.json()["message"] == {
            **message,
            "turn": {**message["turn"], "status": status, "run_id": run_id},
        }
    for target, body in [
        (url, {**payload, "content": "Different"}),
        (url, {**payload, "message_uuid": str(uuid4())}),
        (messages_url, {**append, "content": "Different"}),
    ]:
        response = api_client.post(target, body)
        assert response.status_code == 409
        assert response.json()["error"] == "ERROR_AGENT_MESSAGE_CONFLICT"
    assert (
        AgentMessage.objects.filter(role="user").count() == ChatRun.objects.count() == 2
    )
    created.assert_called_once()
    appended.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["other owner", "other agent"])
def test_conversations_are_private_to_their_owner_and_agent(
    data_fixture, configured_agent, case
):
    owner = data_fixture.create_user()
    other = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner, members=[other])
    agent = configured_agent(workspace=workspace)
    conversation = data_fixture.create_agent_conversation(user=owner, agent=agent)
    message = data_fixture.create_agent_message(conversation=conversation)
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
    assert response.json()["error"] == "ERROR_AGENT_NOT_READY"
    assert "PRIVATE" not in response.content.decode()
    assert not AgentMessage.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("content", [" \n\t", "x" * 100001], ids=["blank", "too-long"])
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
def test_conversations_and_messages_are_paginated_newest_first(
    data_fixture, configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    conversations = []
    for index in range(3):
        with freeze_time(f"2026-10-14 08:0{index}:00"):
            conversations.append(
                data_fixture.create_agent_conversation(
                    user=api_user, agent=agent, title=str(index)
                )
            )
    for index in range(5):
        data_fixture.create_agent_message(
            conversation=conversations[-1], content=str(index)
        )
    # A new message moves its conversation to the top of the list.
    with freeze_time("2026-10-14 08:03:00"):
        AgentService().create_message(
            api_user, agent.id, conversations[0].uuid, uuid4(), "Newest"
        )
    messages_url = agent_url(
        agent, "messages", conversation_uuid=conversations[-1].uuid
    )

    listed = api_client.get(agent_url(agent, "conversations") + "?size=2")
    pages = [
        api_client.get(messages_url + f"?size=2&page={page}").json() for page in (1, 2)
    ]
    missing = api_client.get(agent_url(agent, "messages", conversation_uuid=uuid4()))

    assert [item["title"] for item in listed.json()["results"]] == ["0", "2"]
    assert [[item["content"] for item in page["results"]] for page in pages] == [
        ["3", "4"],
        ["1", "2"],
    ]
    assert api_client.get(messages_url + "?size=101").status_code == 400
    assert missing.status_code == 404
    assert missing.json()["error"] == "ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_equal_timestamp_messages_are_paginated_in_creation_order(
    data_fixture, configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    conversation = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    with freeze_time("2026-10-22 08:00:00"):
        messages = [
            data_fixture.create_agent_message(
                conversation=conversation, uuid=UUID(int=5 - index)
            )
            for index in range(5)
        ]
    url = agent_url(agent, "messages", conversation_uuid=conversation.uuid)

    pages = [
        api_client.get(url + f"?size=2&page={page}").json()["results"]
        for page in (1, 2, 3)
    ]

    assert len({message["created_on"] for page in pages for message in page}) == 1
    expected = [messages[3:5], messages[1:3], messages[:1]]
    assert [[message["id"] for message in page] for page in pages] == [
        [message.id for message in page] for page in expected
    ]
    assert [[message["uuid"] for message in page] for page in pages] == [
        [str(message.uuid) for message in page] for page in expected
    ]


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
    assert (
        AgentConversation.objects.count()
        == AgentMessage.objects.filter(role="user").count()
        == 1
    )


@pytest.mark.django_db
def test_deleting_a_user_removes_their_conversations(data_fixture, configured_agent):
    owner = data_fixture.create_user()
    participant = data_fixture.create_user()
    agent = configured_agent(
        workspace=data_fixture.create_workspace(user=owner, members=[participant])
    )
    data_fixture.create_agent_conversation(user=participant, agent=agent)
    retained = data_fixture.create_agent_conversation(user=owner, agent=agent)

    participant.delete()

    assert list(AgentConversation.objects.all()) == [retained]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("view", ["conversations", "messages"])
def test_independent_conversations_accept_messages_concurrently(
    data_fixture, configured_agent, mocker, view
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversations = [
        data_fixture.create_agent_conversation(user=user, agent=agent) for _ in range(2)
    ]
    barrier = Barrier(2)
    original = AgentService._require_ready

    def both_reach_readiness(service, target):
        original(service, target)
        barrier.wait(timeout=5)

    mocker.patch.object(AgentService, "_require_ready", both_reach_readiness)

    def send(index):
        close_old_connections()
        try:
            actor = get_user_model().objects.get(id=user.id)
            service = AgentService()
            if view == "conversations":
                return service.create_conversation(
                    actor, agent.id, uuid4(), uuid4(), "Hello"
                ).message.id
            return service.create_message(
                actor, agent.id, conversations[index].uuid, uuid4(), "Hello"
            ).message.id
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        message_ids = list(pool.map(send, range(2)))

    assert len(set(message_ids)) == 2
    assert (
        AgentMessage.objects.filter(role="user").count() == ChatRun.objects.count() == 2
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("view", ["conversations", "messages"])
@pytest.mark.parametrize("conflicting_content", [False, True])
def test_concurrent_retries_accept_one_message(
    data_fixture, configured_agent, mocker, view, conflicting_content
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation_uuid, message_uuid = uuid4(), uuid4()
    if view == "messages":
        data_fixture.create_agent_conversation(
            user=user, agent=agent, uuid=conversation_uuid
        )
    barrier = Barrier(2)
    updated = mocker.spy(agent_conversation_updated, "send")
    if view == "conversations":
        original = AgentService._require_ready

        def both_reach_creation(service, target):
            original(service, target)
            barrier.wait(timeout=5)

        mocker.patch.object(AgentService, "_require_ready", both_reach_creation)

    def send(index):
        close_old_connections()
        try:
            actor = get_user_model().objects.get(id=user.id)
            service = AgentService()
            content = "Different" if conflicting_content and index else "Hello"
            if view == "conversations":
                result = service.create_conversation(
                    actor, agent.id, conversation_uuid, message_uuid, content
                )
            else:
                barrier.wait(timeout=5)
                result = service.create_message(
                    actor, agent.id, conversation_uuid, message_uuid, content
                )
            return "created" if result.created else "retried"
        except AgentMessageConflict:
            return "conflict"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))

    assert sorted(results) == (
        ["conflict", "created"] if conflicting_content else ["created", "retried"]
    )
    assert AgentConversation.objects.count() == ChatRun.objects.count() == 1
    assert AgentMessage.objects.filter(role="user").count() == 1
    updated.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_message_rechecks_readiness_after_waiting_for_the_conversation(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    waiting = Event()
    original = AgentHandler.get_conversation

    def get_conversation(handler, *args, **kwargs):
        if kwargs.get("for_update"):
            waiting.set()
        return original(handler, *args, **kwargs)

    mocker.patch.object(AgentHandler, "get_conversation", get_conversation)

    def send():
        close_old_connections()
        try:
            actor = get_user_model().objects.get(id=user.id)
            AgentService().create_message(
                actor, agent.id, conversation.uuid, uuid4(), "Hello"
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            AgentConversation.objects.select_for_update().get(id=conversation.id)
            future = pool.submit(send)
            assert waiting.wait(timeout=5)
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '2s'")
            AgentService().update_configuration(user, agent.id, instructions="")
        with pytest.raises(AgentNotReady):
            future.result(timeout=5)

    assert not AgentMessage.objects.exists()
