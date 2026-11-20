from uuid import uuid4

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.exceptions import (
    AgentConversationDoesNotExist,
    AgentToolApprovalNotPending,
)
from baserow.contrib.agent.models import AgentConversation, AgentMessage
from baserow.contrib.agent.operations import (
    ApproveAgentToolCallsOperationType,
    ContinueAgentTriggeredConversationOperationType,
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
)
from baserow.contrib.agent.service import AgentService
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler

from .utils import agent_url

pytestmark = pytest.mark.django_db


def test_without_rbac_members_chat_and_approve_but_nobody_continues_trigger_runs(
    data_fixture, configured_agent, api_client, api_user
):
    member = data_fixture.create_user()
    agent = configured_agent(user=api_user)
    data_fixture.create_user_workspace(user=member, workspace=agent.workspace)
    conversation = data_fixture.create_shared_agent_conversation(agent=agent)
    data_fixture.create_agent_message(conversation=conversation, role="user")
    approval = data_fixture.create_agent_tool_approval(conversation=conversation)
    sent = data_fixture.create_agent_message(
        conversation=conversation,
        role=AgentMessage.Role.ASSISTANT,
        sender=member,
        unattended=False,
    )

    def allowed(user, operation):
        return CoreHandler().check_permissions(
            user,
            operation.type,
            workspace=agent.workspace,
            context=agent,
            raise_permission_exceptions=False,
        )

    for user in [api_user, member]:
        assert allowed(user, CreateAgentConversationOperationType)
        assert allowed(user, CreateAgentMessageOperationType)
        assert allowed(user, ApproveAgentToolCallsOperationType)
        assert not allowed(user, ContinueAgentTriggeredConversationOperationType)
    response = api_client.post(
        agent_url(agent, "messages", conversation_uuid=conversation.uuid),
        {"uuid": str(uuid4()), "content": "Next"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "PERMISSION_DENIED"
    with pytest.raises(PermissionDenied):
        AgentService().prepare_reply(sent.pk)
    AgentService().prepare_reply(approval.reply.pk, approval_actor_id=member.pk)
    permissions = {
        item["name"]: item["permissions"]
        for item in CoreHandler().get_permissions(member, agent.workspace)
    }
    assert permissions["agent_triggered_conversations"] == {
        "denied_operations": [ContinueAgentTriggeredConversationOperationType.type]
    }


def test_named_approvers_keep_access_and_only_author_can_share_or_delete(
    data_fixture, configured_agent
):
    owner, alice, bob, other = [data_fixture.create_user() for _ in range(4)]
    agent = configured_agent(user=owner)
    for member in (alice, bob, other):
        data_fixture.create_user_workspace(user=member, workspace=agent.workspace)
    conversation = data_fixture.create_agent_conversation(user=owner, agent=agent)
    approval = data_fixture.create_agent_tool_approval(conversation=conversation)
    service = AgentService()

    def request(*users):
        return service.request_approval(
            owner,
            agent.id,
            conversation.uuid,
            approval.reply.uuid,
            [user.pk for user in users],
        )

    with pytest.raises(ValidationError):
        request(alice, data_fixture.create_user())
    assert not service.can_read_conversation(alice, conversation.pk)
    request(alice, bob)
    request(alice, bob)
    assert set(conversation.participants.all()) == {owner, alice, bob}
    assert service.can_follow_conversation(alice, conversation.pk)
    assert not service.can_read_conversation(other, conversation.pk)
    for method in [
        service.delete_for_me,
        service.delete_conversation,
        service.share_conversation,
    ]:
        with pytest.raises(PermissionDenied):
            method(alice, agent.id, conversation.uuid)

    service.delete_for_me(owner, agent.id, conversation.uuid)
    assert not service.can_follow_conversation(owner, conversation.pk)
    with pytest.raises(AgentConversationDoesNotExist):
        service.share_conversation(owner, agent.id, conversation.uuid)
    owner.delete()
    conversation.refresh_from_db()
    assert conversation.owner_user_id is None and not conversation.shared
    assert service.can_read_conversation(bob, conversation.pk)
    service.decide_approvals(
        bob, agent.id, conversation.uuid, [{"id": approval.pk, "approved": True}]
    )
    with pytest.raises(AgentToolApprovalNotPending):
        service.decide_approvals(
            alice, agent.id, conversation.uuid, [{"id": approval.pk, "approved": False}]
        )
    approval.refresh_from_db()
    assert approval.decided_by == bob


def test_sharing_preserves_origin_and_uses_sender_for_each_followup(
    data_fixture, configured_agent
):
    owner, member = data_fixture.create_user(), data_fixture.create_user()
    agent = configured_agent(user=owner)
    data_fixture.create_user_workspace(user=member, workspace=agent.workspace)
    conversation = data_fixture.create_agent_conversation(user=owner, agent=agent)
    service = AgentService()
    for _ in range(2):
        service.share_conversation(owner, agent.id, conversation.uuid)
    conversation.refresh_from_db()
    assert conversation.shared and not conversation.started_by_trigger
    result = service.create_message(
        member, agent.id, conversation.uuid, uuid4(), "Hello"
    )
    assert result.message.sender == member
    assert result.reply.sender == member
    owner.delete()
    conversation.refresh_from_db()
    assert conversation.shared and service.can_read_conversation(
        member, conversation.pk
    )


def test_private_author_deletion_keeps_only_conversations_with_other_participants(
    data_fixture,
):
    owner, member = data_fixture.create_user(), data_fixture.create_user()
    solo = data_fixture.create_agent_conversation(user=owner)
    group = data_fixture.create_agent_conversation(user=owner, agent=solo.agent)
    group.participants.add(member)
    owner.delete()
    assert not AgentConversation.objects.filter(pk=solo.pk).exists()
    group.refresh_from_db()
    assert not group.shared and list(group.participants.all()) == [member]


def test_departed_author_cannot_recover_private_history_with_request_uuids(
    data_fixture, configured_agent
):
    owner, other = data_fixture.create_user(), data_fixture.create_user()
    agent = configured_agent(user=owner)
    data_fixture.create_user_workspace(user=other, workspace=agent.workspace)
    service = AgentService()
    created = service.create_conversation(owner, agent.pk, uuid4(), uuid4(), "Hello")
    created.conversation.participants.add(other)
    service.delete_for_me(owner, agent.pk, created.conversation.uuid)
    with pytest.raises(AgentConversationDoesNotExist):
        service.create_conversation(
            owner, agent.pk, created.conversation.uuid, created.message.uuid, "Hello"
        )
    with pytest.raises(AgentConversationDoesNotExist):
        service.create_message(
            owner, agent.pk, created.conversation.uuid, created.message.uuid, "Hello"
        )
    with pytest.raises(PermissionDenied):
        service.prepare_reply(created.reply.pk)


def test_private_approval_requests_notify_only_current_readers(
    data_fixture, configured_agent, mocker, django_capture_on_commit_callbacks
):
    owner, alice, bob, outsider = [data_fixture.create_user() for _ in range(4)]
    agent = configured_agent(user=owner)
    for member in [alice, bob, outsider]:
        data_fixture.create_user_workspace(user=member, workspace=agent.workspace)
    conversation = data_fixture.create_agent_conversation(agent=agent, user=owner)
    approval = data_fixture.create_agent_tool_approval(conversation=conversation)
    broadcast = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_to_users.delay"
    )
    with django_capture_on_commit_callbacks(execute=True):
        AgentService().request_approval(
            owner, agent.pk, conversation.uuid, approval.reply.uuid, [alice.pk, bob.pk]
        )
    recipients, payload = broadcast.call_args.args
    assert set(recipients) == {owner.pk, alice.pk, bob.pk}
    assert not payload["conversation"]["shared"]
    assert {person["id"] for person in payload["conversation"]["participants"]} == set(
        recipients
    )
    AgentService().share_conversation(owner, agent.pk, conversation.uuid)
    assert AgentService().can_read_conversation(outsider, conversation.pk)
    AgentService().decide_approvals(
        outsider, agent.pk, conversation.uuid, [{"id": approval.pk, "approved": True}]
    )
    approval.refresh_from_db()
    assert approval.decided_by == outsider
