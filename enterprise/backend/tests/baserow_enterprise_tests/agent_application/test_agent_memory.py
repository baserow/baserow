import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.agents import persistent_memory
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import AgentChat, AgentDefinition
from baserow_enterprise.agent_application.tools.memory import (
    AGENT_MEMORY_MAX_LENGTH,
    MEMORY_TOOL_FUNCTIONS,
    remember,
    rewrite_memory,
)

from .test_agent_runner import register_runner_test_model_type


def _ctx(agent):
    return SimpleNamespace(deps=SimpleNamespace(agent=agent))


@pytest.fixture
def agent(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    return AgentApplicationHandler().get_main_agent(application)


@pytest.mark.django_db(transaction=True)
def test_remember_appends_and_survives_concurrent_runs(agent):
    # Two runners hold their own (stale) copies of the agent, as two
    # concurrently running celery tasks would.
    first_copy = AgentDefinition.objects.get(id=agent.id)
    second_copy = AgentDefinition.objects.get(id=agent.id)

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        result = asyncio.run(
            remember(_ctx(first_copy), text="Created table 123.", thought="t")
        )
        assert result == {"success": True}
        result = asyncio.run(
            remember(
                _ctx(second_copy), text="User prefers short summaries.", thought="t"
            )
        )
        assert result == {"success": True}

    agent.refresh_from_db()
    # Neither concurrent append lost the other's note, and the first note
    # doesn't start with a separator newline.
    assert agent.memory == ("Created table 123.\nUser prefers short summaries.")


@pytest.mark.django_db(transaction=True)
def test_remember_respects_size_cap(agent):
    AgentDefinition.objects.filter(id=agent.id).update(
        memory="x" * (AGENT_MEMORY_MAX_LENGTH - 5)
    )
    agent.refresh_from_db()

    result = asyncio.run(remember(_ctx(agent), text="too much now", thought="t"))

    assert "error" in result
    assert "rewrite_memory" in result["error"]


@pytest.mark.django_db(transaction=True)
def test_rewrite_memory_replaces_and_caps(agent):
    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        asyncio.run(remember(_ctx(agent), text="Old note.", thought="t"))
        result = asyncio.run(
            rewrite_memory(_ctx(agent), new_memory="Only this.", thought="t")
        )
        assert result == {"success": True}

    agent.refresh_from_db()
    assert agent.memory == "Only this."

    result = asyncio.run(
        rewrite_memory(
            _ctx(agent), new_memory="x" * (AGENT_MEMORY_MAX_LENGTH + 1), thought="t"
        )
    )
    assert "error" in result


def test_memory_is_injected_into_the_prompt():
    agent = AgentDefinition(memory="Created table 123.")
    prompt = persistent_memory(_ctx(agent))
    assert "<memory>" in prompt
    assert "Created table 123." in prompt

    assert persistent_memory(_ctx(AgentDefinition(memory="  "))) == ""


@pytest.mark.django_db(transaction=True)
def test_memory_tools_available_in_triggered_runs(agent):
    from baserow_enterprise.agent_application.runner import AgentRunner

    register_runner_test_model_type()
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="test-model",
    )
    triggered_chat = AgentChat.objects.create(
        agent=agent, source=AgentChat.Source.TRIGGER, trigger_type="rows_created"
    )

    names = set()
    for toolset in AgentRunner(triggered_chat)._toolsets:
        for tool in getattr(toolset, "tools", {}).values():
            names.add(tool.function.__name__)

    assert {f.__name__ for f in MEMORY_TOOL_FUNCTIONS} <= names


@pytest.mark.django_db
def test_memory_editable_via_api(api_client, data_fixture, agent):
    from django.urls import reverse

    user = agent.application.workspace.workspaceuser_set.first().user
    token = data_fixture.generate_token(user)

    url = reverse("api:agent:agent_item", kwargs={"agent_id": agent.id})
    response = api_client.patch(
        url,
        {"memory": "The user taught me this."},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    assert response.json()["memory"] == "The user taught me this."
    agent.refresh_from_db()
    assert agent.memory == "The user taught me this."
