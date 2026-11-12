import contextlib
from typing import Any

from django.contrib.auth.models import AbstractUser

import pytest

from baserow.contrib.agent.exceptions import AgentConversationReadOnly
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentToolApproval,
)
from baserow.contrib.agent.operations import (
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
    DeleteAgentConversationOperationType,
    ReadAgentConfigurationOperationType,
    ReadAgentConversationsOperationType,
    UpdateAgentConversationOperationType,
)
from baserow.contrib.agent.service import AgentService
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import ExportApplicationsActionType
from baserow.core.handler import CoreHandler
from baserow.core.operations import UpdateApplicationOperationType


def call(
    name: str,
    user: AbstractUser,
    agent: AgentApplication,
    conversation: AgentConversation,
    message: AgentMessage,
    approval: AgentToolApproval,
) -> Any:
    service = AgentService()
    calls = {
        "read configuration": lambda: service.get_configuration(user, agent.id),
        "update configuration": lambda: service.update_configuration(
            user, agent.id, instructions="Changed"
        ),
        "list conversations": lambda: service.list_conversations(user, agent.id),
        "list messages": lambda: service.list_messages(
            user, agent.id, conversation.uuid
        ),
        "retry conversation": lambda: service.create_conversation(
            user, agent.id, conversation.uuid, message.uuid, message.content
        ),
        "retry message": lambda: service.create_message(
            user, agent.id, conversation.uuid, message.uuid, message.content
        ),
        "update conversation": lambda: service.update_conversation(
            user, agent.id, conversation.uuid, title="Renamed"
        ),
        "delete conversation": lambda: service.delete_conversation(
            user, agent.id, conversation.uuid
        ),
        "decide approvals": lambda: service.decide_approvals(
            user, agent.id, conversation.uuid, [{"id": approval.id, "approved": True}]
        ),
        "always allow": lambda: service.decide_approvals(
            user,
            agent.id,
            conversation.uuid,
            [{"id": approval.id, "approved": True}],
            always_allow=True,
        ),
        "export": lambda: action_type_registry.get_by_type(
            ExportApplicationsActionType
        ).do(user, agent.workspace, [agent]),
    }
    return calls[name]()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,operations",
    [
        ("read configuration", [ReadAgentConfigurationOperationType]),
        (
            "update configuration",
            [UpdateApplicationOperationType, ReadAgentConfigurationOperationType],
        ),
        ("list conversations", [ReadAgentConversationsOperationType]),
        ("list messages", [ReadAgentConversationsOperationType]),
        (
            "retry conversation",
            [CreateAgentConversationOperationType, CreateAgentMessageOperationType],
        ),
        ("retry message", [CreateAgentMessageOperationType]),
        ("update conversation", [UpdateAgentConversationOperationType]),
        ("delete conversation", [DeleteAgentConversationOperationType]),
        ("decide approvals", [CreateAgentMessageOperationType]),
        (
            "always allow",
            [
                CreateAgentMessageOperationType,
                UpdateApplicationOperationType,
                ReadAgentConfigurationOperationType,
            ],
        ),
        ("export", [ReadAgentConfigurationOperationType]),
    ],
)
def test_each_call_checks_its_operation_on_the_agent(
    data_fixture, configured_agent, use_tmp_media_root, mocker, name, operations
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    message = data_fixture.create_agent_message(user=user, agent=agent)
    conversation = message.conversation
    approval = data_fixture.create_agent_tool_approval(conversation=conversation)
    check = mocker.spy(CoreHandler, "check_multiple_permissions")

    call(name, user, agent, conversation, message, approval)

    assert [
        (permission.operation_name, permission.context.id)
        for args, _ in check.call_args_list
        for permission in args[1]
    ] == [(operation.type, agent.id) for operation in operations]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,operations",
    [
        ("list messages", [ReadAgentConversationsOperationType]),
        ("retry message", [CreateAgentMessageOperationType]),
        ("decide approvals", [CreateAgentMessageOperationType]),
        (
            "update conversation",
            [UpdateAgentConversationOperationType, UpdateApplicationOperationType],
        ),
        (
            "delete conversation",
            [DeleteAgentConversationOperationType, UpdateApplicationOperationType],
        ),
    ],
)
def test_shared_conversation_calls_also_check_the_agent_update(
    data_fixture, configured_agent, mocker, name, operations
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    conversation = data_fixture.create_shared_agent_conversation(agent=agent)
    message = data_fixture.create_agent_message(
        conversation=conversation, role="trigger"
    )
    approval = data_fixture.create_agent_tool_approval(conversation=conversation)
    check = mocker.spy(CoreHandler, "check_multiple_permissions")

    with contextlib.suppress(AgentConversationReadOnly):
        call(name, user, agent, conversation, message, approval)

    assert [
        (permission.operation_name, permission.context.id)
        for args, _ in check.call_args_list
        for permission in args[1]
    ] == [(operation.type, agent.id) for operation in operations]
