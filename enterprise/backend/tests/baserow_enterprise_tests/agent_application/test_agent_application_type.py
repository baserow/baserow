from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.agents.service import AgentService
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import (
    AgentApplication,
    AgentChat,
    AgentDefinition,
)


@pytest.mark.django_db
def test_create_agent_application_inits_agent_and_integration(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    application = CoreHandler().create_application(
        user, workspace, "agent", init_with_data=True, name="Product owner"
    )
    application = application.specific

    assert isinstance(application, AgentApplication)
    agent = AgentApplicationHandler().get_main_agent(application)
    assert agent.name == "Product owner"

    integration = LocalBaserowIntegration.objects.get(application=application)
    assert integration.authorized_user_id == user.id


@pytest.mark.django_db
def test_update_agent_application_identity_syncs_integrations(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = CoreHandler().create_application(
        user, workspace, "agent", init_with_data=True, name="Agent"
    )
    identity = AgentService().create_agent(user, workspace, name="Agent identity")

    CoreHandler().update_application(
        user, application.specific, agent_identity_id=identity.id
    )

    application.refresh_from_db()
    assert application.specific.agent_identity_id == identity.id
    integration = LocalBaserowIntegration.objects.get(application=application)
    assert integration.authorized_agent_id == identity.id

    CoreHandler().update_application(user, application.specific, agent_identity_id=None)
    integration.refresh_from_db()
    assert integration.authorized_agent_id is None


@pytest.mark.django_db
def test_update_agent_application_identity_must_be_in_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    application = CoreHandler().create_application(
        user, workspace, "agent", init_with_data=True, name="Agent"
    )
    other_identity = AgentService().create_agent(user, other_workspace, name="Other")

    with pytest.raises(DRFValidationError):
        CoreHandler().update_application(
            user, application.specific, agent_identity_id=other_identity.id
        )


@pytest.mark.django_db
def test_export_import_agent_application(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    identity = AgentService().create_agent(user, workspace, name="Identity")
    AgentApplicationHandler().set_agent_identity(application, identity)

    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        instructions="You are the product owner.",
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-test",
        ai_temperature=0.4,
    )
    AgentChat.objects.create(agent=agent)

    application_type = application_type_registry.get("agent")
    config = ImportExportConfig(include_permission_data=False)
    serialized = application_type.export_serialized(application, config)

    assert len(serialized["agents"]) == 1
    assert serialized["agents"][0]["instructions"] == "You are the product owner."
    assert "chats" not in serialized

    imported = application_type.import_serialized(
        workspace, serialized, config, {}
    ).specific

    assert imported.id != application.id
    # The identity must not survive a non-publishing import.
    assert imported.agent_identity_id is None
    imported_agent = AgentApplicationHandler().get_main_agent(imported)
    assert imported_agent.instructions == "You are the product owner."
    assert imported_agent.ai_generative_ai_model == "gpt-test"
    assert AgentChat.objects.filter(agent__application=imported).count() == 0


@pytest.mark.django_db
def test_only_one_agent_definition_per_application(data_fixture):
    from django.db import IntegrityError

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )

    with pytest.raises(IntegrityError):
        AgentDefinition.objects.create(application=application, name="Second")


@pytest.mark.django_db
def test_create_agent_application_with_setup_fields(data_fixture):
    from baserow.contrib.integrations.core.models import CorePeriodicService

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        application = (
            CoreHandler()
            .create_application(
                user,
                workspace,
                "agent",
                init_with_data=True,
                name="Company finder",
                description="Find startups.",
                instructions="## Goal\nFind startups.",
                run_mode="weekly",
                permissions="ask_first",
                web_search=True,
                create_identity=True,
            )
            .specific
        )

    agent = AgentApplicationHandler().get_main_agent(application)
    assert agent.instructions == "## Goal\nFind startups."

    identity = application.agent_identity
    assert identity is not None
    assert identity.name == "Company finder"
    assert identity.workspace_id == workspace.id
    integration = LocalBaserowIntegration.objects.get(application=application)
    assert integration.authorized_agent_id == identity.id

    tools = {tool.type: tool for tool in agent.tools.all()}
    assert tools["workspace"].config == {
        "access": "everything",
        "require_write_approval": True,
        "tool_rules": {},
    }
    assert "web_search" in tools

    trigger = application.triggers.get()
    service = trigger.service.specific
    assert isinstance(service, CorePeriodicService)
    assert service.interval == "WEEK"
    assert service.hour == 9
    assert service.minute == 0
    assert service.day_of_week == 0

    # The wizard replaced the setup conversation.
    assert not AgentChat.objects.filter(agent=agent).exists()


@pytest.mark.django_db
def test_create_agent_application_setup_presets(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    read_only = (
        CoreHandler()
        .create_application(
            user,
            workspace,
            "agent",
            init_with_data=True,
            name="Reader",
            run_mode="daily",
            permissions="read_only",
        )
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(read_only)
    assert agent.tools.get(type="workspace").config["access"] == "read_only"
    assert read_only.triggers.get().service.specific.interval == "DAY"
    assert read_only.agent_identity is None

    free = (
        CoreHandler()
        .create_application(
            user,
            workspace,
            "agent",
            init_with_data=True,
            name="Free",
            run_mode="chat",
            permissions="free",
        )
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(free)
    config = agent.tools.get(type="workspace").config
    assert config["access"] == "everything"
    assert config["require_write_approval"] is False
    assert not free.triggers.exists()


@pytest.mark.django_db
def test_create_agent_application_with_existing_identity(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = AgentService().create_agent(user, workspace, name="Investor")

    application = (
        CoreHandler()
        .create_application(
            user,
            workspace,
            "agent",
            init_with_data=True,
            name="Outreach",
            agent_identity_id=identity.id,
        )
        .specific
    )
    assert application.agent_identity_id == identity.id

    other_workspace = data_fixture.create_workspace(user=user)
    with pytest.raises(DRFValidationError):
        CoreHandler().create_application(
            user,
            other_workspace,
            "agent",
            init_with_data=True,
            name="Outreach",
            agent_identity_id=identity.id,
        )


@pytest.mark.django_db
def test_create_identity_requires_permission(data_fixture):
    from baserow.core.exceptions import PermissionException

    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    member = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="MEMBER"
    )

    with pytest.raises(PermissionException):
        CoreHandler().create_application(
            member,
            workspace,
            "agent",
            init_with_data=True,
            name="Agent",
            create_identity=True,
        )
