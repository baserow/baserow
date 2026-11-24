from unittest.mock import patch
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

pytestmark = pytest.mark.django_db


def test_without_rbac_members_chat_and_approve_but_nobody_continues_trigger_runs(
    data_fixture, configured_agent
):
    owner, member = data_fixture.create_user(), data_fixture.create_user()
    agent = configured_agent(user=owner)
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

    for user in [owner, member]:
        assert allowed(user, CreateAgentConversationOperationType)
        assert allowed(user, CreateAgentMessageOperationType)
        assert allowed(user, ApproveAgentToolCallsOperationType)
        assert not allowed(user, ContinueAgentTriggeredConversationOperationType)
    with pytest.raises(PermissionDenied):
        AgentService().prepare_reply(sent.pk)
    AgentService().prepare_reply(approval.reply.pk, approver_id=member.pk)


def test_named_approvers_keep_access_and_only_author_can_share_or_delete(
    data_fixture, configured_agent
):
    owner = data_fixture.create_user()
    alice, bob, other = [
        data_fixture.create_user(first_name=name) for name in ["Alice", "Bob", "Other"]
    ]
    agent = configured_agent(user=owner)
    for member in (alice, bob, other):
        data_fixture.create_user_workspace(user=member, workspace=agent.workspace)
    data_fixture.create_identity(workspace=agent.workspace)
    conversation = data_fixture.create_agent_conversation(user=owner, agent=agent)
    solo = data_fixture.create_agent_conversation(user=owner, agent=agent)
    service = AgentService()

    def request(*users):
        return service.request_approval(
            owner, agent.id, conversation.uuid, [user.pk for user in users]
        )

    def candidates(search="", limit=10):
        return service.list_approver_candidates(
            owner, agent.id, conversation.uuid, search, limit
        )

    assert candidates() == []
    with pytest.raises(AgentToolApprovalNotPending):
        request(alice)
    data_fixture.create_agent_message(conversation=conversation, sender=owner)
    approval = data_fixture.create_agent_tool_approval(conversation=conversation)
    assert candidates() == [alice, bob, other]
    assert candidates(limit=2) == [alice, bob]
    assert candidates("ali") == [alice]
    with pytest.raises(ValidationError):
        request(alice, data_fixture.create_user())
    assert not service.can_read_conversation(alice, conversation.pk)
    request(alice, bob)
    request(alice, bob)
    assert set(conversation.participants.all()) == {owner, alice, bob}
    assert candidates() == [other]
    assert service.can_follow_conversation(alice, conversation.pk)
    with patch.object(
        AgentService, "_can_read_agent_conversations", return_value=False
    ):
        assert not service.can_follow_conversation(alice, conversation.pk)
        assert service.can_follow_conversation(owner, conversation.pk)
    assert not service.can_read_conversation(other, conversation.pk)
    with pytest.raises(PermissionDenied):
        service.delete_conversation(alice, agent.id, conversation.uuid)
    with pytest.raises(AgentConversationDoesNotExist):
        service.share_conversation(alice, agent.id, conversation.uuid)

    service.leave_conversation(owner, agent.id, conversation.uuid)
    assert not service.can_follow_conversation(owner, conversation.pk)
    with pytest.raises(AgentConversationDoesNotExist):
        service.share_conversation(owner, agent.id, conversation.uuid)
    owner.delete()
    assert not AgentConversation.objects.filter(pk=solo.pk).exists()
    conversation.refresh_from_db()
    assert conversation.owner_user_id is None and not conversation.shared
    assert set(conversation.participants.all()) == {alice, bob}
    assert service.can_read_conversation(bob, conversation.pk)
    service.decide_approvals(
        bob, agent.id, conversation.uuid, [{"id": approval.pk, "approved": True}]
    )
    resumed = service.prepare_reply(approval.reply.pk, approver_id=bob.pk)
    assert resumed.conversation_user is None and resumed.timezone is None
    with pytest.raises(AgentToolApprovalNotPending):
        service.decide_approvals(
            alice, agent.id, conversation.uuid, [{"id": approval.pk, "approved": False}]
        )
    approval.refresh_from_db()
    assert approval.decided_by == bob

    assert not service.leave_conversation(bob, agent.id, conversation.uuid).trashed
    assert set(conversation.participants.all()) == {alice}
    service.leave_conversation(alice, agent.id, conversation.uuid)
    assert not AgentConversation.objects_and_trash.filter(pk=conversation.pk).exists()


def test_departed_author_cannot_recover_private_history_with_request_uuids(
    data_fixture, configured_agent
):
    owner, other = data_fixture.create_user(), data_fixture.create_user()
    agent = configured_agent(user=owner)
    data_fixture.create_user_workspace(user=other, workspace=agent.workspace)
    service = AgentService()
    created = service.create_conversation(owner, agent.pk, uuid4(), uuid4(), "Hello")
    created.conversation.participants.add(other)
    service.leave_conversation(owner, agent.pk, created.conversation.uuid)
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
            owner, agent.pk, conversation.uuid, [alice.pk, bob.pk]
        )
    recipients, payload = broadcast.call_args.args
    assert set(recipients) == {owner.pk, alice.pk, bob.pk}
    assert not payload["conversation"]["shared"]
    assert {person["id"] for person in payload["conversation"]["participants"]} == set(
        recipients
    )
