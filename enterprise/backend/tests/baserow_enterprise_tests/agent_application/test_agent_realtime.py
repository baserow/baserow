import uuid
from unittest.mock import patch

import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.agent_application.actions import (
    CreateAgentChatChannelActionType,
    DeleteAgentTriggerActionType,
    UpdateAgentChatChannelActionType,
    UpdateAgentTriggerActionType,
)
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.tools.handler import AgentToolHandler
from baserow_enterprise.agent_application.triggers.handler import (
    AgentTriggerHandler,
)

BROADCAST = (
    "baserow_enterprise.agent_application.ws.receivers.broadcast_to_channel_group"
)
WEB_SOCKET_ID = "socket-of-the-editing-tab"


@pytest.fixture
def setup(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    user.web_socket_id = WEB_SOCKET_ID
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    return user, session_id, application, agent


def _events(broadcast, event_type):
    return [
        call.args
        for call in broadcast.delay.call_args_list
        if call.args[1]["type"] == event_type
    ]


@pytest.mark.django_db
def test_configuration_changes_are_broadcast_with_their_payload_except_to_the_sender(
    setup, django_capture_on_commit_callbacks
):
    user, session_id, application, agent = setup

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        trigger = AgentTriggerHandler().create_trigger(user, application, "periodic")
    (created,) = _events(broadcast, "agent_trigger_created")
    assert created[0] == f"agent_application-{application.id}"
    assert created[1]["application_id"] == application.id
    assert created[1]["trigger"]["id"] == trigger.id
    assert created[1]["trigger"]["service_type"] == "periodic"
    # The editing tab applied the change from the response already.
    assert created[2] == WEB_SOCKET_ID

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        UpdateAgentTriggerActionType.do(user, trigger, enabled=False)
    (updated,) = _events(broadcast, "agent_trigger_updated")
    assert updated[1]["trigger"]["enabled"] is False
    assert updated[2] == WEB_SOCKET_ID

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        tool = AgentToolHandler().create_tool(
            user, agent, "service", name="Mail", service_type_str="smtp_email"
        )
    (created,) = _events(broadcast, "agent_tool_created")
    assert created[1]["tool"]["id"] == tool.id
    assert created[1]["tool"]["service_type"] == "smtp_email"
    assert created[2] == WEB_SOCKET_ID

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        AgentToolHandler().trash_tool(user, tool)
    (deleted,) = _events(broadcast, "agent_tool_deleted")
    assert deleted[1] == {
        "type": "agent_tool_deleted",
        "tool_id": tool.id,
        "application_id": application.id,
    }
    assert deleted[2] == WEB_SOCKET_ID

    # A restore is nobody's edit, so every tab, the restoring one included,
    # gets the tool back.
    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        TrashHandler.restore_item(user, "agent_tool", tool.id)
    (restored,) = _events(broadcast, "agent_tool_created")
    assert restored[1]["tool"]["id"] == tool.id
    assert restored[2] is None


@pytest.mark.django_db
def test_undo_and_redo_are_broadcast_to_the_undoing_session_too(
    setup, django_capture_on_commit_callbacks
):
    user, session_id, application, agent = setup
    trigger = AgentTriggerHandler().create_trigger(user, application, "periodic")
    UpdateAgentTriggerActionType.do(
        user, trigger, service_values={"interval": "DAY", "hour": 9, "minute": 0}
    )
    UpdateAgentTriggerActionType.do(
        user, trigger, service_values={"interval": "HOUR", "hour": 9, "minute": 0}
    )
    scopes = [ApplicationActionScopeType.value(application.id)]

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        ActionHandler.undo(user, scopes, session_id)
    (updated,) = _events(broadcast, "agent_trigger_updated")
    assert updated[1]["trigger"]["service"]["interval"] == "DAY"
    # The core undo handler clears the web socket id so the form in the
    # undoing tab follows the reverted value as well.
    assert updated[2] is None

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        ActionHandler.redo(user, scopes, session_id)
    (updated,) = _events(broadcast, "agent_trigger_updated")
    assert updated[1]["trigger"]["service"]["interval"] == "HOUR"
    assert updated[2] is None

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        DeleteAgentTriggerActionType.do(user, trigger)
        ActionHandler.undo(user, scopes, session_id)
    (deleted,) = _events(broadcast, "agent_trigger_deleted")
    assert deleted[1]["trigger_id"] == trigger.id
    (restored,) = _events(broadcast, "agent_trigger_created")
    assert restored[1]["trigger"]["id"] == trigger.id
    assert restored[2] is None


@pytest.mark.django_db
def test_channel_events_carry_the_public_config_only(
    setup, django_capture_on_commit_callbacks
):
    user, session_id, application, agent = setup

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        channel = CreateAgentChatChannelActionType.do(
            user,
            application,
            "slack",
            name="Slack",
            config={"bot_token": "xoxb-secret", "signing_secret": "sign"},
        )
    (created,) = _events(broadcast, "agent_chat_channel_created")
    assert created[1]["channel"]["id"] == channel.id
    assert "xoxb-secret" not in str(created[1])
    assert "sign" != created[1]["channel"]["config"].get("signing_secret")
    assert created[2] == WEB_SOCKET_ID

    with (
        patch(BROADCAST) as broadcast,
        django_capture_on_commit_callbacks(execute=True),
    ):
        UpdateAgentChatChannelActionType.do(user, channel, name="Renamed")
    (updated,) = _events(broadcast, "agent_chat_channel_updated")
    assert updated[1]["channel"]["name"] == "Renamed"
    assert "xoxb-secret" not in str(updated[1])
