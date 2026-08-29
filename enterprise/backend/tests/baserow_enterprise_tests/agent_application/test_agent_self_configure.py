import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.ai_models import AgentModelProfile
from baserow_enterprise.agent_application.deps import ToolHelpers
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatMessage,
    AgentTool,
    AgentTrigger,
)
from baserow_enterprise.agent_application.tools.self_configure import (
    add_own_trigger,
    disable_own_tools,
    enable_own_tools,
    update_own_instructions,
)

from .test_agent_runner import register_runner_test_model_type


def _ctx(agent, chat):
    deps = SimpleNamespace(
        user=None,
        workspace=agent.application.workspace,
        agent=agent,
        chat=chat,
        tool_helpers=ToolHelpers(
            update_status=lambda s: None,
            navigate_to=lambda loc: "",
            model_profile=AgentModelProfile(None, {}),
        ),
    )
    return SimpleNamespace(deps=deps)


@pytest.fixture
def configured_agent(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    return user, workspace, application, agent


@pytest.mark.django_db(transaction=True)
def test_update_own_instructions(configured_agent):
    user, workspace, application, agent = configured_agent
    chat = AgentChat.objects.create(agent=agent, user=user)

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        result = asyncio.run(
            update_own_instructions(
                _ctx(agent, chat), instructions="Be helpful.", thought="t"
            )
        )

    assert result == {"success": True}
    agent.refresh_from_db()
    assert agent.instructions == "Be helpful."


@pytest.mark.django_db(transaction=True)
def test_update_own_instructions_requires_permission(data_fixture, configured_agent):
    user, workspace, application, agent = configured_agent
    outsider = data_fixture.create_user()
    chat = AgentChat.objects.create(agent=agent, user=outsider)

    result = asyncio.run(
        update_own_instructions(_ctx(agent, chat), instructions="Hax", thought="t")
    )

    assert "error" in result
    agent.refresh_from_db()
    assert agent.instructions != "Hax"


@pytest.mark.django_db(transaction=True)
def test_set_own_trigger_and_toggle_tools(data_fixture, configured_agent):
    user, workspace, application, agent = configured_agent
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    chat = AgentChat.objects.create(agent=agent, user=user)

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        result = asyncio.run(
            add_own_trigger(
                _ctx(agent, chat),
                service_type="local_baserow_rows_created",
                thought="t",
                table_id=table.id,
            )
        )
        trigger = AgentTrigger.objects.get(application=application)
        assert result == {"success": True, "trigger_id": trigger.id}
        assert trigger.service.specific.table_id == table.id
        # The service was bound to the application's integration.
        assert trigger.service.integration_id is not None

        result = asyncio.run(
            enable_own_tools(
                _ctx(agent, chat), types=["workspace", "web_search"], thought="t"
            )
        )
        assert result == {"success": True}
        assert set(
            AgentTool.objects.filter(agent=agent).values_list("type", flat=True)
        ) == {"workspace", "web_search"}

        result = asyncio.run(
            disable_own_tools(_ctx(agent, chat), types=["web_search"], thought="t")
        )
        assert result == {"success": True}
        assert set(
            AgentTool.objects.filter(agent=agent).values_list("type", flat=True)
        ) == {"workspace"}


@pytest.mark.django_db(transaction=True)
def test_create_with_description_starts_setup_chat(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with (
        patch(
            "baserow_enterprise.agent_application.tasks.run_agent_chat.delay"
        ) as delay_mock,
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        application = (
            CoreHandler()
            .create_application(
                user,
                workspace,
                "agent",
                init_with_data=True,
                name="PO",
                description="Prioritize the feature roadmap in the features table.",
            )
            .specific
        )

    agent = AgentApplicationHandler().get_main_agent(application)
    # A workspace model was picked automatically so the setup can run.
    assert agent.ai_generative_ai_type
    assert agent.ai_generative_ai_model

    chat = AgentChat.objects.get(agent=agent)
    assert chat.source == AgentChat.Source.SETUP
    assert chat.user_id == user.id
    message = chat.messages.get(role=AgentChatMessage.Role.SYSTEM)
    assert "Prioritize the feature roadmap" in message.content
    delay_mock.assert_called_once()


@pytest.mark.django_db
def test_create_without_description_does_not_start_setup(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )

    agent = AgentApplicationHandler().get_main_agent(application)
    assert not AgentChat.objects.filter(agent=agent).exists()


@pytest.mark.django_db(transaction=True)
def test_triggered_runs_never_get_self_configuration_tools(configured_agent):
    from baserow_enterprise.agent_application.runner import AgentRunner
    from baserow_enterprise.agent_application.tools.self_configure import (
        SELF_CONFIGURE_TOOL_FUNCTIONS,
    )

    user, workspace, application, agent = configured_agent
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="test-model",
    )
    self_configure_names = {f.__name__ for f in SELF_CONFIGURE_TOOL_FUNCTIONS}

    def toolset_function_names(chat):
        names = set()
        for toolset in AgentRunner(chat)._toolsets:
            for tool in getattr(toolset, "tools", {}).values():
                names.add(tool.function.__name__)
        return names

    triggered_chat = AgentChat.objects.create(
        agent=agent, source=AgentChat.Source.TRIGGER, trigger_type="rows_created"
    )
    assert toolset_function_names(triggered_chat) & self_configure_names == set()

    manual_chat = AgentChat.objects.create(
        agent=agent, user=user, source=AgentChat.Source.MANUAL
    )
    assert self_configure_names <= toolset_function_names(manual_chat)

    # Even a triggered chat later continued by a human keeps the agent unable
    # to reconfigure itself, because the chat has no owning user.
    continued_trigger_chat = AgentChat.objects.create(
        agent=agent, source=AgentChat.Source.TRIGGER, trigger_type="rows_created"
    )
    assert (
        toolset_function_names(continued_trigger_chat) & self_configure_names == set()
    )


@pytest.mark.django_db(transaction=True)
def test_self_configure_tools_reject_chats_without_user(configured_agent):
    user, workspace, application, agent = configured_agent
    chat = AgentChat.objects.create(
        agent=agent, source=AgentChat.Source.TRIGGER, trigger_type="rows_created"
    )

    result = asyncio.run(
        update_own_instructions(_ctx(agent, chat), instructions="Hax", thought="t")
    )

    assert "error" in result
    agent.refresh_from_db()
    assert agent.instructions != "Hax"
