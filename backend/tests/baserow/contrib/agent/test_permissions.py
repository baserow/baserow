import pytest

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.operations import (
    CreateAgentConversationOperationType,
    CreateAgentMessageOperationType,
    ReadAgentConversationsOperationType,
    ReadAgentSettingsOperationType,
)
from baserow.contrib.agent.service import AgentService
from baserow.core.handler import CoreHandler
from baserow.core.operations import (
    ReadApplicationOperationType,
    UpdateApplicationOperationType,
)
from baserow.core.registries import ImportExportConfig


def call(name, user, agent, conversation, message):
    service = AgentService()
    calls = {
        "readiness": lambda: service.get_readiness(user, agent.id),
        "read settings": lambda: service.get_configuration(user, agent.id),
        "update settings": lambda: service.update_configuration(
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
        "export": lambda: AgentApplicationType().export_serialized(
            agent, ImportExportConfig(include_permission_data=False, exported_by=user)
        ),
    }
    return calls[name]()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,operations",
    [
        ("readiness", [ReadApplicationOperationType]),
        ("read settings", [ReadAgentSettingsOperationType]),
        ("update settings", [UpdateApplicationOperationType]),
        ("list conversations", [ReadAgentConversationsOperationType]),
        ("list messages", [ReadAgentConversationsOperationType]),
        (
            "retry conversation",
            [CreateAgentConversationOperationType, CreateAgentMessageOperationType],
        ),
        ("retry message", [CreateAgentMessageOperationType]),
        ("export", [ReadAgentSettingsOperationType]),
    ],
)
def test_each_call_checks_its_operation_on_the_agent(
    data_fixture, configured_agent, mocker, name, operations
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    message = data_fixture.create_agent_message(user=user, agent=agent)
    conversation = message.conversation
    check = mocker.spy(CoreHandler, "check_permissions")

    call(name, user, agent, conversation, message)

    assert [
        (args[2], kwargs["context"].id) for args, kwargs in check.call_args_list
    ] == [(operation.type, agent.id) for operation in operations]
