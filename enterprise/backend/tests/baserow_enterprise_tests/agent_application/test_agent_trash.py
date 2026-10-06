from unittest.mock import patch

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.services.models import Service
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.agent_application.channels.handler import (
    AgentChatChannelHandler,
)
from baserow_enterprise.agent_application.channels.registries import (
    start_channel_chat,
)
from baserow_enterprise.agent_application.channels.web import (
    WebAgentChatChannelType,
)
from baserow_enterprise.agent_application.exceptions import (
    AgentChatChannelDoesNotExist,
    AgentChatDoesNotExist,
    AgentDefinitionDoesNotExist,
    AgentToolDoesNotExist,
    AgentTriggerDoesNotExist,
)
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatChannel,
    AgentChatMessage,
)
from baserow_enterprise.agent_application.tools.handler import AgentToolHandler
from baserow_enterprise.agent_application.triggers.handler import (
    AgentTriggerHandler,
)

from .test_agent_runner import register_runner_test_model_type


@pytest.fixture
def agent_setup(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    application.active = True
    application.save(update_fields=["active"])
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent, ai_generative_ai_type="agent_runner_test", ai_generative_ai_model="m"
    )
    trigger = AgentTriggerHandler().create_trigger(user, application, "periodic")
    tool = AgentToolHandler().create_tool(
        user, agent, "service", service_type_str="smtp_email"
    )
    slack = AgentChatChannel.objects.create(
        application=application,
        type="slack",
        name="Slack",
        config={"bot_token": "xoxb", "signing_secret": "s"},
    )
    web_type = WebAgentChatChannelType()
    web = AgentChatChannel.objects.create(
        application=application,
        type="web",
        name="Web",
        config=web_type.prepare_config({}),
    )
    chat = AgentChat.objects.create(agent=agent, user=user, source="manual")
    return user, workspace, application, agent, trigger, tool, slack, web, chat


def _lookups(agent, trigger, tool, slack, web, chat):
    return [
        (
            lambda: AgentApplicationHandler().get_agent(agent.id),
            AgentDefinitionDoesNotExist,
        ),
        (
            lambda: AgentChatHandler().get_chat_by_uuid(chat.uuid),
            AgentChatDoesNotExist,
        ),
        (
            lambda: AgentTriggerHandler().get_trigger(trigger.id),
            AgentTriggerDoesNotExist,
        ),
        (lambda: AgentToolHandler().get_tool(tool.id), AgentToolDoesNotExist),
        (
            lambda: AgentChatChannelHandler().get_channel(slack.id),
            AgentChatChannelDoesNotExist,
        ),
        (
            lambda: AgentChatChannelHandler().get_channel_by_uid(slack.uid),
            AgentChatChannelDoesNotExist,
        ),
    ]


@pytest.mark.django_db
def test_trashed_agent_is_unreachable_and_restorable(agent_setup):
    user, workspace, application, agent, trigger, tool, slack, web, chat = agent_setup
    slug = web.config["slug"]

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        CoreHandler().delete_application(user, application)

    for lookup, exception in _lookups(agent, trigger, tool, slack, web, chat):
        with pytest.raises(exception):
            lookup()
    assert AgentChatHandler().get_public_web_channel(slug) is None
    # Inbound Slack messages are dropped while the agent is in the trash.
    assert start_channel_chat(slack, "C1|1.0", "hello") is None
    assert chat.messages.count() == 0

    TrashHandler.restore_item(user, "application", application.id)

    for lookup, _ in _lookups(agent, trigger, tool, slack, web, chat):
        lookup()
    assert AgentChatHandler().get_public_web_channel(slug) == web


@pytest.mark.django_db
def test_trashed_workspace_hides_the_agent_too(agent_setup):
    user, workspace, application, agent, trigger, tool, slack, web, chat = agent_setup

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        CoreHandler().delete_workspace(user, workspace)

    with pytest.raises(AgentDefinitionDoesNotExist):
        AgentApplicationHandler().get_agent(agent.id)
    assert AgentChatHandler().get_public_web_channel(web.config["slug"]) is None


@pytest.mark.django_db
def test_trashing_an_agent_cancels_its_running_chats(agent_setup):
    user, workspace, application, agent, trigger, tool, slack, web, chat = agent_setup
    chat.status = AgentChat.Status.IN_PROGRESS
    chat.save(update_fields=["status"])
    paused = AgentChat.objects.create(
        agent=agent, user=user, source="manual", status="awaiting_approval"
    )

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        CoreHandler().delete_application(user, application)

    chat.refresh_from_db()
    paused.refresh_from_db()
    assert chat.status == AgentChat.Status.CANCELING
    # Approvals stay pending so a restored agent can still be resumed.
    assert paused.status == AgentChat.Status.AWAITING_APPROVAL


@pytest.mark.django_db
def test_queued_run_of_a_trashed_agent_does_not_start(agent_setup):
    from baserow_enterprise.agent_application.tasks import _execute_agent_chat_turn

    user, workspace, application, agent, trigger, tool, slack, web, chat = agent_setup
    message = AgentChatHandler().create_message(
        chat, AgentChatMessage.Role.HUMAN, "Hello"
    )
    chat.status = AgentChat.Status.IN_PROGRESS
    chat.save(update_fields=["status"])
    application.trashed = True
    application.save(update_fields=["trashed"])

    with (
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
        patch("baserow_enterprise.agent_application.runner.AgentRunner") as runner,
    ):
        _execute_agent_chat_turn(chat.id, message.id)

    runner.assert_not_called()
    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.IDLE
    assert chat.messages.filter(role=AgentChatMessage.Role.AI).count() == 0


@pytest.mark.django_db
def test_permanently_deleting_an_agent_removes_its_services(agent_setup):
    user, workspace, application, agent, trigger, tool, slack, web, chat = agent_setup
    service_ids = [trigger.service_id, tool.service_id]
    assert Service.objects.filter(id__in=service_ids).count() == 2

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        CoreHandler().delete_application(user, application)
        TrashHandler.permanently_delete(application)

    assert Service.objects.filter(id__in=service_ids).count() == 0
    assert not AgentChat.objects.filter(id=chat.id).exists()


@pytest.mark.django_db
def test_deleting_chats_keeps_the_pending_approvals_count_in_sync(agent_setup):
    from baserow_enterprise.agent_application.models import AgentChatToolApproval
    from baserow_enterprise.agent_application.tasks import clean_up_old_agent_chats

    user, workspace, application, agent, trigger, tool, slack, web, chat = agent_setup
    chat.status = AgentChat.Status.AWAITING_APPROVAL
    chat.save(update_fields=["status"])
    AgentChatToolApproval.objects.create(
        chat=chat, tool_call_id="c1", tool_name="send_email", tool_args={}
    )

    with (
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ) as group,
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_permitted_users"
        ) as permitted,
    ):
        AgentChatHandler().delete_chat(chat)

    assert group.delay.call_args.args[1]["type"] == "agent_chat_deleted"
    payload = permitted.delay.call_args.args[4]
    assert payload == {
        "type": "agent_pending_approvals_updated",
        "application_id": application.id,
        "count": 0,
    }

    # The retention cleanup announces its deletions the same way.
    from datetime import timedelta

    from django.utils import timezone

    old = AgentChat.objects.create(agent=agent, source="trigger", status="idle")
    AgentChat.objects.filter(id=old.id).update(
        updated_on=timezone.now() - timedelta(days=3650)
    )
    with (
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ) as group,
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_permitted_users"
        ),
    ):
        clean_up_old_agent_chats()
    assert not AgentChat.objects.filter(id=old.id).exists()
    assert any(
        call.args[1] == {"type": "agent_chat_deleted", "chat_id": old.id}
        for call in group.delay.call_args_list
    )
