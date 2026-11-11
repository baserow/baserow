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
    DeleteAgentConversationActionType,
    UpdateAgentConversationActionType,
)
from baserow.contrib.agent.exceptions import (
    AgentConversationDoesNotExist,
    AgentMessageConflict,
    AgentNotReady,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentConversation, AgentMessage
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.signals import agent_conversation_activity
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.exceptions import FeatureDisabledException
from baserow.core.models import TrashEntry
from baserow.core.trash.exceptions import CannotRestoreItemNotOwnedByUser
from baserow.core.trash.handler import TrashHandler

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
    message, reply = AgentMessage.objects.order_by("id")
    run_id = str(ChatRun.objects.get().id)

    assert response.json() == {
        "conversation": {
            "id": conversation.id,
            "uuid": payload["uuid"],
            "title": "Hello world " + "x" * 238,
            "created_on": ANY,
            "updated_on": ANY,
            "run_id": run_id,
            "pending_approval_count": 0,
            "pinned": False,
        },
        "message": {
            "id": message.id,
            "uuid": payload["message_uuid"],
            "role": "user",
            "content": payload["content"],
            "created_on": ANY,
            "status": None,
            "error_code": "",
            "run_id": None,
            "steps": None,
            "approvals": [],
        },
        "reply": {
            "id": reply.id,
            "uuid": str(reply.uuid),
            "role": "assistant",
            "content": "",
            "created_on": ANY,
            "status": "running",
            "error_code": "",
            "run_id": run_id,
            "steps": None,
            "approvals": [],
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
@pytest.mark.parametrize("write", ["conversation", "message", "decision"])
def test_agents_answer_nothing_while_the_feature_is_off(
    data_fixture, configured_agent, settings, write
):
    """An Agent imported while the feature is off must not call its provider."""

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    approval = data_fixture.create_agent_tool_approval(conversation=conversation)
    settings.FEATURE_FLAGS = []
    service = AgentService()

    with pytest.raises(FeatureDisabledException):
        if write == "conversation":
            service.create_conversation(user, agent.id, uuid4(), uuid4(), "Hi")
        elif write == "message":
            service.create_message(user, agent.id, conversation.uuid, uuid4(), "Hi")
        else:
            service.decide_approvals(
                user,
                agent.id,
                conversation.uuid,
                [{"id": approval.id, "approved": True}],
            )

    assert not ChatRun.objects.exists()


@pytest.mark.django_db
def test_failed_first_message_leaves_no_conversation_or_action(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    registered = mocker.spy(
        CreateAgentConversationActionType, "send_action_done_signal"
    )
    mocker.patch.object(ChatRunHandler, "start_run", side_effect=RuntimeError)

    with pytest.raises(RuntimeError):
        action_type_registry.get_by_type(CreateAgentConversationActionType).do(
            user, agent.id, uuid4(), uuid4(), "Hi"
        )

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
    current_conversation = api_client.get(url).json()["results"][0]
    # Accepted retries and conflicts must not depend on the current readiness.
    agent.instructions = ""
    agent.save()

    for target, body, accepted, changed in [
        (
            url,
            payload,
            first,
            {"status": "completed", "content": "Hello from the agent", "run_id": None},
        ),
        (
            messages_url,
            {"uuid": payload["message_uuid"], "content": payload["content"]},
            first,
            {"status": "completed", "content": "Hello from the agent", "run_id": None},
        ),
        (messages_url, append, second, {}),
    ]:
        retried = api_client.post(target, body).json()
        assert retried["message"] == accepted.json()["message"]
        # The reply is live state: the first one finished since its response.
        assert retried["reply"] == {**accepted.json()["reply"], **changed}
        # An old reply's retry must not clear the newer reply's activity indicator.
        assert retried["conversation"] == current_conversation
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
def test_retrying_legacy_messages_only_returns_their_own_reply(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    first, second = [
        data_fixture.create_agent_message(conversation=conversation, content=content)
        for content in ["First", "Following"]
    ]
    reply = data_fixture.create_agent_message(
        conversation=conversation,
        role="assistant",
        content="Answer",
        status="completed",
    )
    service = AgentService()

    for message, expected_reply in [(first, None), (second, reply)]:
        retried = service.create_message(
            user, agent.id, conversation.uuid, message.uuid, message.content
        )

        assert retried.message == message
        assert retried.reply == expected_reply
        assert retried.run_id is None
        assert not retried.created


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
    approval = data_fixture.create_agent_tool_approval(conversation=conversation)
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
        lambda: service.update_conversation(
            actor, target.id, conversation.uuid, title="Renamed"
        ),
        lambda: service.delete_conversation(actor, target.id, conversation.uuid),
        lambda: service.decide_approvals(
            actor, target.id, conversation.uuid, [{"id": approval.id, "approved": True}]
        ),
    ]:
        with pytest.raises(AgentConversationDoesNotExist):
            attempt()
    assert AgentMessage.objects.count() == 2
    approval.refresh_from_db()
    assert approval.status == "pending"
    assert AgentConversation.objects.get().title == conversation.title


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

    listed = api_client.get(agent_url(agent, "conversations") + "?limit=2")
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
def test_the_next_conversations_page_continues_after_the_previous_one(
    data_fixture, configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    with freeze_time("2026-10-14 08:00:00"):
        oldest, *others = [
            data_fixture.create_agent_conversation(
                user=api_user, agent=agent, title=str(index)
            )
            for index in range(4)
        ]
    url = agent_url(agent, "conversations")
    first = api_client.get(url, {"limit": 2}).json()
    # Deleting a listed conversation or moving an unlisted one up shifts no page.
    AgentService().delete_conversation(api_user, agent.id, others[-1].uuid)
    with freeze_time("2026-10-14 08:01:00"):
        AgentService().create_message(api_user, agent.id, oldest.uuid, uuid4(), "Hi")

    second = api_client.get(url, {"limit": 2, "cursor": first["next_cursor"]}).json()

    assert [item["title"] for item in first["results"]] == ["3", "2"]
    assert [item["title"] for item in second["results"]] == ["1"]
    assert second["next_cursor"] is None
    for params in [{"cursor": "nope"}, {"limit": 101}]:
        assert api_client.get(url, params).status_code == 400


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
            action_type_registry.get_by_type(CreateAgentConversationActionType).do(
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
    assert (AgentConversation.objects.count(), AgentMessage.objects.count()) == (1, 2)


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
    # An eager reply would also check readiness and wait at the barrier.
    mocker.patch.object(ChatRunHandler, "_enqueue")

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
    activity = mocker.spy(agent_conversation_activity, "send")
    # An eager reply would wait at the barrier and notify again when it ends.
    mocker.patch.object(ChatRunHandler, "_enqueue")
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
    activity.assert_called_once()


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


@pytest.mark.django_db
def test_updating_a_title_collapses_whitespace_and_keeps_the_list_order(
    data_fixture, configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    renamed = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    newer = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    url = agent_url(agent, "conversation", conversation_uuid=renamed.uuid)

    response = api_client.patch(url, {"title": "  Daily\n research "})
    listed = api_client.get(agent_url(agent, "conversations")).json()["results"]

    assert response.status_code == 200
    assert response.json()["title"] == "Daily research"
    assert [item["uuid"] for item in listed] == [str(newer.uuid), str(renamed.uuid)]
    blank = api_client.patch(url, {"title": " \n"})
    assert blank.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert api_client.patch(url, {}).json()["title"] == "Daily research"
    assert (
        Action.objects.filter(type=UpdateAgentConversationActionType.type).count() == 1
    )


@pytest.mark.django_db
def test_a_deleted_conversation_stops_its_reply_and_only_its_owner_restores_it(
    data_fixture,
    configured_agent,
    api_client,
    api_user,
    django_capture_on_commit_callbacks,
):
    member = data_fixture.create_user()
    agent = configured_agent(
        workspace=data_fixture.create_workspace(user=api_user, members=[member])
    )
    payload = new_conversation()
    api_client.post(agent_url(agent, "conversations"), payload)
    url = agent_url(agent, "conversation", conversation_uuid=payload["uuid"])
    messages_url = agent_url(agent, "messages", conversation_uuid=payload["uuid"])

    with django_capture_on_commit_callbacks(execute=True):
        assert api_client.delete(url).status_code == 204

    reply = AgentMessage.objects.get(role="assistant")
    assert ChatRun.objects.get().status == reply.status == "cancelled"
    assert not api_client.get(agent_url(agent, "conversations")).json()["results"]
    for response in [
        api_client.get(messages_url),
        api_client.post(messages_url, {"uuid": str(uuid4()), "content": "Hello"}),
        api_client.post(agent_url(agent, "conversations"), payload),
        api_client.patch(url, {"title": "Renamed"}),
        api_client.post(
            agent_url(agent, "approvals", conversation_uuid=payload["uuid"]),
            {"decisions": [{"id": 1, "approved": True}]},
        ),
        api_client.delete(url),
    ]:
        assert response.json()["error"] == "ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST"
    entry = TrashEntry.objects.get()
    assert (entry.trash_item_type, entry.trash_item_owner, entry.application_id) == (
        "agent_conversation",
        api_user,
        agent.id,
    )
    with pytest.raises(CannotRestoreItemNotOwnedByUser):
        TrashHandler.restore_item(member, "agent_conversation", entry.trash_item_id)

    TrashHandler.restore_item(api_user, "agent_conversation", entry.trash_item_id)

    assert api_client.get(messages_url).json()["count"] == 2
    api_client.delete(url)
    TrashHandler.empty(api_user, agent.workspace_id, agent.id)
    TrashHandler.permanently_delete_marked_trash()
    assert not AgentConversation.objects_and_trash.exists()
    assert not AgentMessage.objects.exists()


@pytest.mark.django_db
def test_deleting_an_owner_removes_their_trashed_conversations_from_the_trash(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    agent = configured_agent(user=owner)
    conversation = data_fixture.create_agent_conversation(user=owner, agent=agent)
    AgentService().delete_conversation(owner, agent.id, conversation.uuid)

    owner.delete()

    assert not TrashEntry.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_updating_and_deleting_can_be_undone_and_redone(data_fixture, configured_agent):
    user = data_fixture.create_user(session_id="session")
    agent = configured_agent(user=user)
    conversation = data_fixture.create_agent_conversation(
        user=user, agent=agent, title="Original"
    )
    scopes = [ApplicationActionScopeType.value(agent.id)]
    action_type_registry.get_by_type(UpdateAgentConversationActionType).do(
        user, agent.id, conversation.uuid, title="Renamed", pinned=True
    )
    action_type_registry.get_by_type(DeleteAgentConversationActionType).do(
        user, agent.id, conversation.uuid
    )

    ActionHandler.undo(user, scopes, "session")
    assert AgentConversation.objects.get().title == "Renamed"
    assert AgentConversation.objects.get().pinned is True
    ActionHandler.undo(user, scopes, "session")
    assert AgentConversation.objects.get().title == "Original"
    assert AgentConversation.objects.get().pinned is False

    ActionHandler.redo(user, scopes, "session")
    ActionHandler.redo(user, scopes, "session")
    assert not AgentConversation.objects.exists()
    assert AgentConversation.trash.get().title == "Renamed"
    assert AgentConversation.trash.get().pinned is True


@pytest.mark.django_db
def test_pin_uses_the_update_endpoint_without_changing_activity(
    data_fixture, configured_agent, api_client, api_user, mocker
):
    agent = configured_agent(user=api_user)
    old = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    recent = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    updated_on = old.updated_on
    changed = mocker.patch(
        "baserow.contrib.agent.service.agent_conversation_updated.send"
    )
    url = agent_url(agent, "conversation", conversation_uuid=old.uuid)
    list_url = agent_url(agent, "conversations")

    response = api_client.patch(url, {"pinned": True})
    assert response.status_code == 200
    assert response.json()["pinned"] is True
    assert [row["id"] for row in api_client.get(list_url).json()["results"]] == [
        old.id,
        recent.id,
    ]
    old.refresh_from_db()
    assert old.updated_on == updated_on
    assert changed.call_args.kwargs["values"] == {"pinned": True}
    assert api_client.patch(url, {"pinned": False}).json()["pinned"] is False
    assert [row["id"] for row in api_client.get(list_url).json()["results"]] == [
        recent.id,
        old.id,
    ]
    assert api_client.patch(url, {"pinned": "invalid"}).status_code == 400
    foreign = data_fixture.create_agent_conversation(agent=agent)
    assert (
        api_client.patch(
            agent_url(agent, "conversation", conversation_uuid=foreign.uuid),
            {"pinned": True},
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_conversation_filters_and_cursors_cover_the_pin_boundary(
    data_fixture, configured_agent, api_client, api_user
):
    agent = configured_agent(user=api_user)
    with freeze_time("2026-11-11 10:00:00"):
        pinned = [
            data_fixture.create_agent_conversation(
                user=api_user, agent=agent, pinned=True
            )
            for _ in range(3)
        ]
    with freeze_time("2026-11-11 11:00:00"):
        recent = [
            data_fixture.create_agent_conversation(user=api_user, agent=agent)
            for _ in range(3)
        ]
    for item in [pinned[0], pinned[2], recent[0], recent[2]]:
        for _ in range(2):
            data_fixture.create_agent_tool_approval(conversation=item)
    # Other owners, other agents, and trash remain invisible through every filter.
    for item in [
        data_fixture.create_agent_conversation(agent=agent, pinned=True),
        data_fixture.create_agent_conversation(user=api_user, pinned=True),
        data_fixture.create_agent_conversation(
            user=api_user, agent=agent, pinned=True, trashed=True
        ),
    ]:
        data_fixture.create_agent_tool_approval(conversation=item)
    url = agent_url(agent, "conversations")
    for filters, expected in [
        ({}, pinned[::-1] + recent[::-1]),
        ({"pinned": "true"}, pinned[::-1]),
        ({"pinned": "false"}, recent[::-1]),
        (
            {"has_pending_approvals": "true"},
            [pinned[2], pinned[0], recent[2], recent[0]],
        ),
        ({"has_pending_approvals": "false"}, [pinned[1], recent[1]]),
        ({"pinned": "true", "has_pending_approvals": "true"}, [pinned[2], pinned[0]]),
    ]:
        params = {"limit": 2, **filters}
        ids = []
        while True:
            response = api_client.get(url, params)
            assert response.status_code == 200
            data = response.json()
            ids.extend(row["id"] for row in data["results"])
            if data["next_cursor"] is None:
                break
            params["cursor"] = data["next_cursor"]
        assert ids == [item.id for item in expected]
    for params in [
        {"pinned": "bad"},
        {"has_pending_approvals": "bad"},
        {"cursor": "2:1_1"},
    ]:
        assert api_client.get(url, params).status_code == 400
