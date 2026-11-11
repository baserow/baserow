from functools import partial
from unittest.mock import MagicMock, call
from uuid import UUID, uuid4

from django.db import transaction

import pytest
from pytest_mock import MockerFixture
from rest_framework.fields import DateTimeField

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    CreateAgentMessageActionType,
    DecideAgentToolApprovalsActionType,
    DeleteAgentConversationActionType,
    UpdateAgentConversationActionType,
)
from baserow.contrib.agent.models import (
    AgentConversation,
    AgentMessage,
)
from baserow.contrib.agent.signals import agent_conversation_activity
from baserow.core.action.registries import action_type_registry
from baserow.core.agents.service import AgentService as IdentityService
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.models import Agent
from baserow.core.signals import application_pending_count_updated
from baserow.core.trash.handler import TrashHandler


def conversation_write(data_fixture, user, agent, kind):
    if kind == "message":
        conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
        return partial(
            CreateAgentMessageActionType.do,
            user,
            agent.id,
            conversation.uuid,
            uuid4(),
            "PRIVATE MESSAGE",
        )
    return partial(
        CreateAgentConversationActionType.do,
        user,
        agent.id,
        uuid4(),
        uuid4(),
        "PRIVATE MESSAGE",
    )


@pytest.fixture
def pending_count_updated(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(application_pending_count_updated, "send")


def update_of(
    conversation: AgentConversation,
    run_id: UUID | None = None,
    pending_approval_count: int = 0,
) -> dict:
    return {
        "type": "agent_conversation_activity",
        "agent_id": conversation.agent_id,
        "conversation_uuid": str(conversation.uuid),
        "conversation": {
            "id": conversation.id,
            "uuid": str(conversation.uuid),
            "title": conversation.title,
            "created_on": DateTimeField().to_representation(conversation.created_on),
            "updated_on": DateTimeField().to_representation(conversation.updated_on),
            "run_id": str(run_id) if run_id else None,
            "pending_approval_count": pending_approval_count,
            "pinned": conversation.pinned,
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["conversation", "message"])
def test_a_reply_start_and_end_notify_only_the_owner_after_commit_and_not_on_retry(
    data_fixture, configured_agent, mocker, django_capture_on_commit_callbacks, kind
):
    user = data_fixture.create_user(web_socket_id="source-tab")
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[other_user])
    agent = configured_agent(workspace=workspace)
    write = conversation_write(data_fixture, user, agent, kind)
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_users.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        result = write()
        broadcast.assert_not_called()

    # The sending tab has the start from its response; every tab needs the end.
    ended = AgentConversation.objects.get(id=result.conversation.id)
    assert broadcast.call_args_list == [
        call(
            [user.id],
            update_of(result.conversation, result.run_id),
            ignore_web_socket_id="source-tab",
        ),
        call([user.id], update_of(ended), ignore_web_socket_id=None),
    ]

    with django_capture_on_commit_callbacks(execute=True):
        retried = write()

    assert retried.message.id == result.message.id
    assert not retried.created
    assert broadcast.call_count == 2


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["conversation", "message"])
def test_rolled_back_content_does_not_notify_other_sessions(
    data_fixture, configured_agent, mocker, django_capture_on_commit_callbacks, kind
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    write = conversation_write(data_fixture, user, agent, kind)
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_users.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                write()
                raise RuntimeError("Abort the outer transaction")

    assert not AgentMessage.objects.exists()
    broadcast.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["create", "rename", "trash", "restore", "delete"])
def test_identity_changes_queue_one_invalidation_after_commit(
    data_fixture, mocker, django_capture_on_commit_callbacks, change
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = Agent.objects.create(workspace=workspace, name="PRIVATE IDENTITY")
    identity_id = identity.id
    identities = IdentityService()
    if change in {"restore", "delete"}:
        identities.delete_agent(user, identity)
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_run_as_updates.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            if change == "create":
                identity_id = identities.create_agent(
                    user, workspace, name="PRIVATE NEW IDENTITY"
                ).id
            elif change == "rename":
                identities.update_agent(user, identity, name="PRIVATE NEW NAME")
            elif change == "trash":
                identities.delete_agent(user, identity)
            elif change == "restore":
                TrashHandler.restore_item(user, "agent", identity.id)
            else:
                TrashHandler.permanently_delete(identity)
            broadcast.assert_not_called()

    broadcast.assert_called_once_with(workspace.id, identity_id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values",
    [
        {},
        {"name": "Original"},
        {"role_uid": "ADMIN"},
        {"name": "Original", "role_uid": "ADMIN"},
    ],
)
def test_unchanged_identity_name_does_not_invalidate_run_as_options(
    data_fixture, mocker, django_capture_on_commit_callbacks, values
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = Agent.objects.create(workspace=workspace, name="Original")
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_run_as_updates.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        IdentityService().update_agent(user, identity, **values)

    broadcast.assert_not_called()


@pytest.mark.django_db
def test_rolled_back_identity_change_does_not_invalidate_configuration(
    data_fixture, mocker, django_capture_on_commit_callbacks
):
    user = data_fixture.create_user()
    application = data_fixture.create_agent_application(user=user)
    identity = Agent.objects.create(workspace=application.workspace, name="Original")
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_run_as_updates.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                IdentityService().update_agent(user, identity, name="Rolled back")
                raise RuntimeError("Abort identity change")

    identity.refresh_from_db()
    assert identity.name == "Original"
    broadcast.assert_not_called()


@pytest.mark.django_db
def test_renames_pins_deletions_and_restores_notify_only_the_owner(
    data_fixture,
    configured_agent,
    mocker,
    django_capture_on_commit_callbacks,
    pending_count_updated,
):
    user = data_fixture.create_user(web_socket_id="source-tab")
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[other_user])
    agent = configured_agent(workspace=workspace)
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    event = {"agent_id": agent.id, "conversation_uuid": str(conversation.uuid)}
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_users.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        action_type_registry.get_by_type(UpdateAgentConversationActionType).do(
            user, agent.id, conversation.uuid, title="Renamed", pinned=True
        )
        action_type_registry.get_by_type(DeleteAgentConversationActionType).do(
            user, agent.id, conversation.uuid
        )
        TrashHandler.restore_item(user, "agent_conversation", conversation.id)

    conversation.refresh_from_db()
    assert broadcast.call_args_list == [
        call(
            [user.id],
            {
                "type": "agent_conversation_updated",
                **event,
                "values": {"title": "Renamed", "pinned": True},
            },
            ignore_web_socket_id="source-tab",
        ),
        call(
            [user.id],
            {"type": "agent_conversation_deleted", **event},
            ignore_web_socket_id="source-tab",
        ),
        # The restoring tab also needs it back in its list.
        call([user.id], update_of(conversation), ignore_web_socket_id=None),
    ]
    pending_count_updated.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["pending", "approved", "rejected"])
def test_trash_and_restore_only_notify_counts_when_approvals_are_pending(
    data_fixture, mocker, django_capture_on_commit_callbacks, status
):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    reply = data_fixture.create_agent_message(
        conversation=conversation, role="assistant", status="waiting"
    )
    data_fixture.create_agent_tool_approval(reply=reply, status=status)
    queued = mocker.patch(
        "baserow.ws.signals.broadcast_application_pending_counts.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        action_type_registry.get_by_type(DeleteAgentConversationActionType).do(
            user, agent.id, conversation.uuid
        )
        queued.assert_not_called()
    assert queued.call_count == (1 if status == "pending" else 0)

    queued.reset_mock()
    with django_capture_on_commit_callbacks(execute=True):
        TrashHandler.restore_item(user, "agent_conversation", conversation.id)
        queued.assert_not_called()
    assert queued.call_count == (1 if status == "pending" else 0)
    if status == "pending":
        queued.assert_called_once_with(agent.id, [user.id])


@pytest.mark.django_db
def test_rolled_back_conversation_trash_does_not_notify_pending_counts(
    data_fixture, mocker, django_capture_on_commit_callbacks
):
    reply = data_fixture.create_agent_message(role="assistant", status="waiting")
    data_fixture.create_agent_tool_approval(reply=reply)
    conversation = reply.conversation
    queued = mocker.patch(
        "baserow.ws.signals.broadcast_application_pending_counts.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                action_type_registry.get_by_type(DeleteAgentConversationActionType).do(
                    conversation.owner_user, conversation.agent_id, conversation.uuid
                )
                raise RuntimeError("Abort conversation deletion")

    queued.assert_not_called()
    conversation.refresh_from_db()
    assert not conversation.trashed


@pytest.mark.django_db
def test_a_deleted_conversation_sends_no_reply_activity(
    data_fixture, mocker, django_capture_on_commit_callbacks
):
    conversation = data_fixture.create_agent_conversation(trashed=True)
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_users.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        agent_conversation_activity.send(None, conversation=conversation, user=None)

    broadcast.assert_not_called()


@pytest.mark.django_db
def test_every_decision_tells_the_owner_s_other_sessions_what_is_left_to_decide(
    data_fixture,
    configured_agent,
    mocker,
    django_capture_on_commit_callbacks,
):
    user = data_fixture.create_user(web_socket_id="source-tab")
    agent = configured_agent(user=user)
    reply = data_fixture.create_agent_message(
        user=user, agent=agent, role="assistant", status="waiting"
    )
    first, last = [
        data_fixture.create_agent_tool_approval(reply=reply) for _ in range(2)
    ]
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_users.delay"
    )
    # A resumed reply would notify again when it ends.
    mocker.patch.object(ChatRunHandler, "_enqueue")

    expected = []
    for approval, left in [(first, 1), (last, 0)]:
        with django_capture_on_commit_callbacks(execute=True):
            result = action_type_registry.get_by_type(
                DecideAgentToolApprovalsActionType
            ).do(
                user,
                agent.id,
                reply.conversation.uuid,
                [{"id": approval.id, "approved": True}],
            )
        conversation = AgentConversation.objects.get(id=reply.conversation_id)
        expected.append(
            call(
                [user.id],
                update_of(conversation, result.run_id, left),
                ignore_web_socket_id="source-tab",
            )
        )

    assert broadcast.call_args_list == expected
