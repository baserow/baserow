import pytest

from baserow.contrib.builder.workflow_actions.models import AIAgentWorkflowAction
from baserow.contrib.integrations.ai.models import AIIntegration
from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.ai_provider.registries import (
    ai_provider_model_feature_type_registry,
)
from baserow.core.trash.handler import TrashHandler


def test_ai_agent_feature_type_is_registered():
    feature_type = ai_provider_model_feature_type_registry.get(
        AI_PROVIDER_FEATURE_AI_AGENT
    )
    assert feature_type.supports_default_model is False


@pytest.mark.django_db
def test_ai_agent_availability_lists_only_feature_models(data_fixture, settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    workspace = data_fixture.create_workspace()
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="agent-model",
        feature_types=[AI_PROVIDER_FEATURE_AI_AGENT],
    )
    AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="fields-only-model",
        feature_types=["ai_fields"],
    )

    availability = ai_provider_model_feature_type_registry.get_workspace_availability(
        workspace
    )[AI_PROVIDER_FEATURE_AI_AGENT]

    assert availability["is_enabled"] is True
    assert availability["models"] == {"openai": ["agent-model"]}


@pytest.mark.django_db
def test_agent_selection_does_not_block_model_deletion(data_fixture, settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="agent-model",
        feature_types=[AI_PROVIDER_FEATURE_AI_AGENT],
    )

    AIProviderHandler.delete_model(model)

    assert not AIProviderModel.objects.filter(id=model.id).exists()


@pytest.mark.django_db
def test_ai_agent_count_model_references(data_fixture):
    service = data_fixture.create_ai_agent_service(
        ai_generative_ai_type="openai",
        ai_generative_ai_model="agent-model",
    )
    integration = service.integration
    workspace = integration.application.workspace
    data_fixture.create_ai_agent_service(
        integration=integration,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="another-model",
    )
    data_fixture.create_ai_agent_service(
        integration=integration,
        ai_generative_ai_type="anthropic",
        ai_generative_ai_model="agent-model",
    )
    data_fixture.create_ai_agent_service(
        integration=integration,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="agent-model",
        trashed=True,
    )
    other_service = data_fixture.create_ai_agent_service(
        ai_generative_ai_type="openai",
        ai_generative_ai_model="agent-model",
    )
    other_workspace = other_service.integration.application.workspace
    feature_type = ai_provider_model_feature_type_registry.get(
        AI_PROVIDER_FEATURE_AI_AGENT
    )

    assert feature_type.count_model_references("openai", "agent-model", workspace) == 1
    assert (
        feature_type.count_model_references("openai", "agent-model", other_workspace)
        == 1
    )
    assert feature_type.count_model_references("openai", "agent-model", None) == 2
    assert feature_type.count_model_references("openai", "unknown-model", None) == 0
    assert feature_type.count_model_references("mistral", "agent-model", None) == 0


@pytest.mark.django_db
def test_ai_agent_count_model_references_ignores_trashed_ancestors(data_fixture):
    service = data_fixture.create_ai_agent_service(
        ai_generative_ai_type="openai",
        ai_generative_ai_model="agent-model",
    )
    application = service.integration.application
    workspace = application.workspace
    feature_type = ai_provider_model_feature_type_registry.get(
        AI_PROVIDER_FEATURE_AI_AGENT
    )
    assert feature_type.count_model_references("openai", "agent-model", None) == 1

    application.trashed = True
    application.save()

    assert feature_type.count_model_references("openai", "agent-model", None) == 0
    assert feature_type.count_model_references("openai", "agent-model", workspace) == 0

    application.trashed = False
    application.save()
    workspace.trashed = True
    workspace.save()

    assert feature_type.count_model_references("openai", "agent-model", None) == 0


@pytest.mark.django_db
def test_ai_agent_count_model_references_skips_services_without_integration(
    data_fixture,
):
    data_fixture.create_ai_agent_service(
        integration=None,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="agent-model",
    )
    feature_type = ai_provider_model_feature_type_registry.get(
        AI_PROVIDER_FEATURE_AI_AGENT
    )

    assert feature_type.count_model_references("openai", "agent-model", None) == 0
    assert (
        feature_type.count_model_references(
            "openai", "agent-model", data_fixture.create_workspace()
        )
        == 0
    )


@pytest.mark.django_db
def test_ai_agent_count_model_references_ignores_trashed_automation_owners(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    integration = data_fixture.create_integration(
        AIIntegration, application=workflow.automation, user=user
    )
    node = data_fixture.create_automation_node(
        user=user,
        workflow=workflow,
        type="ai_agent",
        service=data_fixture.create_ai_agent_service(
            integration=integration,
            ai_generative_ai_type="openai",
            ai_generative_ai_model="agent-model",
        ),
    )
    workspace = workflow.automation.workspace
    feature_type = ai_provider_model_feature_type_registry.get(
        AI_PROVIDER_FEATURE_AI_AGENT
    )
    assert feature_type.count_model_references("openai", "agent-model", None) == 1
    assert feature_type.count_model_references("openai", "agent-model", workspace) == 1

    TrashHandler.trash(user, workspace, workflow.automation, node)

    assert feature_type.count_model_references("openai", "agent-model", None) == 0
    assert feature_type.count_model_references("openai", "agent-model", workspace) == 0

    TrashHandler.restore_item(user, "automation_node", node.id)

    assert feature_type.count_model_references("openai", "agent-model", None) == 1

    TrashHandler.trash(user, workspace, workflow.automation, workflow)

    assert feature_type.count_model_references("openai", "agent-model", None) == 0


@pytest.mark.django_db
def test_ai_agent_count_model_references_ignores_trashed_builder_owners(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    service = data_fixture.create_ai_agent_service(
        integration=data_fixture.create_integration(
            AIIntegration, application=page.builder, user=user
        ),
        ai_generative_ai_type="openai",
        ai_generative_ai_model="agent-model",
    )
    action = data_fixture.create_workflow_action(
        AIAgentWorkflowAction, page=page, element=element, service=service
    )
    workspace = page.builder.workspace
    feature_type = ai_provider_model_feature_type_registry.get(
        AI_PROVIDER_FEATURE_AI_AGENT
    )
    assert feature_type.count_model_references("openai", "agent-model", workspace) == 1

    action.trashed = True
    action.save()

    assert feature_type.count_model_references("openai", "agent-model", workspace) == 0

    action.trashed = False
    action.save()
    TrashHandler.trash(user, workspace, page.builder, element)

    assert feature_type.count_model_references("openai", "agent-model", workspace) == 0

    TrashHandler.restore_item(user, "builder_element", element.id)
    TrashHandler.trash(user, workspace, page.builder, page)

    assert feature_type.count_model_references("openai", "agent-model", workspace) == 0
