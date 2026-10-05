import asyncio
from unittest.mock import patch

from django.urls import reverse

import pytest
from pydantic_ai.toolsets import FunctionToolset

from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.skills.handler import WorkspaceSkillHandler
from baserow_enterprise.agent_application.agents import workspace_skills
from baserow_enterprise.agent_application.application_types import (
    AgentApplicationType,
)
from baserow_enterprise.agent_application.deps import AgentRunDeps
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import AgentSkill
from baserow_enterprise.agent_application.tools.skills import build_skills_toolset


@pytest.fixture
def agent_setup(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="A")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    handler = WorkspaceSkillHandler()
    formulas = handler.create_skill(
        workspace,
        name="Formulas",
        description="Use when writing Baserow formulas.",
        content="Always wrap field names in field('...').",
    )
    tone = handler.create_skill(
        workspace, name="Tone", description="How we talk.", content="Be brief."
    )
    return user, workspace, application, agent, formulas, tone


def _deps(agent, agent_skills):
    deps = AgentRunDeps.__new__(AgentRunDeps)
    deps.skills = agent_skills
    deps.agent = agent
    return deps


class _Ctx:
    def __init__(self, deps):
        self.deps = deps


@pytest.mark.django_db
def test_set_agent_skills_and_prompt_layers(agent_setup):
    user, workspace, application, agent, formulas, tone = agent_setup

    AgentApplicationHandler().set_agent_skills(
        agent,
        [
            {"skill_id": tone.id, "mode": "always"},
            {"skill_id": formulas.id, "mode": "on_demand"},
        ],
    )
    links = list(agent.agent_skills.select_related("skill").order_by("order"))
    assert [(link.skill.name, link.mode, link.order) for link in links] == [
        ("Tone", "always", 0),
        ("Formulas", "on_demand", 1),
    ]

    prompt = workspace_skills(_Ctx(_deps(agent, links)))
    assert '<skill name="Tone">\nBe brief.\n</skill>' in prompt
    assert "call `load_skill`" in prompt
    assert "- Formulas: Use when writing Baserow formulas." in prompt
    # On-demand content is not inlined.
    assert "field('...')" not in prompt

    assert workspace_skills(_Ctx(_deps(agent, []))) == ""

    # Replacing keeps only the new set.
    AgentApplicationHandler().set_agent_skills(agent, [{"skill_id": formulas.id}])
    assert list(agent.agent_skills.values_list("skill__name", "mode")) == [
        ("Formulas", "always")
    ]


@pytest.mark.django_db
def test_set_agent_skills_rejects_other_workspaces(agent_setup, data_fixture):
    user, workspace, application, agent, formulas, tone = agent_setup
    from baserow.core.skills.exceptions import WorkspaceSkillDoesNotExist

    other = data_fixture.create_workspace(user=user)
    foreign = WorkspaceSkillHandler().create_skill(other, name="Foreign")
    with pytest.raises(WorkspaceSkillDoesNotExist):
        AgentApplicationHandler().set_agent_skills(agent, [{"skill_id": foreign.id}])
    assert agent.agent_skills.count() == 0


@pytest.mark.django_db
def test_load_skill_tool_reads_preloaded_skills(agent_setup):
    user, workspace, application, agent, formulas, tone = agent_setup
    link = AgentSkill(agent=agent, skill=formulas, mode="on_demand")
    toolset = build_skills_toolset()
    assert isinstance(toolset, FunctionToolset)
    tool = toolset.tools["load_skill"]

    ctx = _Ctx(_deps(agent, [link]))
    assert asyncio.run(tool.function(ctx, name="Formulas")) == (
        "Always wrap field names in field('...')."
    )
    assert "Unknown skill 'Nope'" in asyncio.run(tool.function(ctx, name="Nope"))


@pytest.mark.django_db
def test_update_agent_api_sets_skills(api_client, data_fixture, agent_setup):
    user, workspace, application, agent, formulas, tone = agent_setup
    token = data_fixture.generate_token(user)
    url = reverse("api:agent:agent_item", kwargs={"agent_id": agent.id})

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        response = api_client.patch(
            url,
            {"skills": [{"skill_id": formulas.id, "mode": "on_demand"}]},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == 200, response.json()
    assert response.json()["skills"] == [
        {
            "id": agent.agent_skills.get().id,
            "skill_id": formulas.id,
            "name": "Formulas",
            "description": "Use when writing Baserow formulas.",
            "mode": "on_demand",
            "order": 0,
        }
    ]

    response = api_client.patch(
        url,
        {"skills": [{"skill_id": 999999}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 404
    assert response.json()["error"] == "ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST"

    # Deleting the workspace skill unlinks it from the agent.
    WorkspaceSkillHandler().delete_skill(formulas)
    assert agent.agent_skills.count() == 0


@pytest.mark.django_db
def test_duplicate_keeps_skill_links_but_export_drops_them(agent_setup):
    user, workspace, application, agent, formulas, tone = agent_setup
    AgentApplicationHandler().set_agent_skills(
        agent, [{"skill_id": tone.id, "mode": "always"}]
    )
    app_type = AgentApplicationType()

    exported = app_type.export_serialized(
        application, ImportExportConfig(include_permission_data=False)
    )
    assert exported["agents"][0]["skills"] == []

    duplicate_config = ImportExportConfig(
        include_permission_data=True, is_duplicate=True
    )
    exported = app_type.export_serialized(application, duplicate_config)
    assert exported["agents"][0]["skills"] == [{"skill_id": tone.id, "mode": "always"}]

    imported = app_type.import_serialized(workspace, exported, duplicate_config, {})
    copy_agent = AgentApplicationHandler().get_main_agent(imported.specific)
    assert list(copy_agent.agent_skills.values_list("skill_id", "mode")) == [
        (tone.id, "always")
    ]


@pytest.mark.django_db
def test_create_agent_application_with_skills(agent_setup):
    user, workspace, application, agent, formulas, tone = agent_setup

    created = (
        CoreHandler()
        .create_application(
            user,
            workspace,
            "agent",
            init_with_data=True,
            name="Writer",
            skills=[
                {"skill_id": tone.id, "mode": "on_demand"},
                {"skill_id": formulas.id},
            ],
        )
        .specific
    )
    created_agent = AgentApplicationHandler().get_main_agent(created)
    assert list(
        created_agent.agent_skills.order_by("order").values_list("skill_id", "mode")
    ) == [(tone.id, "on_demand"), (formulas.id, "always")]

    from rest_framework.exceptions import ValidationError as DRFValidationError

    with pytest.raises(DRFValidationError):
        CoreHandler().create_application(
            user,
            workspace,
            "agent",
            init_with_data=True,
            name="Broken",
            skills=[{"skill_id": 999999}],
        )
