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
