import json
from unittest.mock import patch

import pytest

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.integrations.ai.integration_types import AIIntegrationType
from baserow.contrib.integrations.ai.service_types import AIAgentServiceType
from baserow.core.generative_ai.exceptions import GenerativeAIPromptError
from baserow.core.integrations.service import IntegrationService
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.test_utils.helpers import AnyInt
from baserow.test_utils.pytest_conftest import FakeDispatchContext


def mock_ai_prompt(return_value="AI response", should_fail=False):
    """
    Context manager to mock AI model prompt calls.
    """

    def _prompt(
        model, prompt, workspace=None, temperature=None, settings_override=None
    ):
        if should_fail:
            raise GenerativeAIPromptError("AI API error")
        return return_value

    return patch(
        "baserow.core.generative_ai.generative_ai_model_types.OpenAIGenerativeAIModelType.prompt",
        side_effect=_prompt,
    )


@pytest.mark.django_db
def test_ai_agent_service_creation(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'Tell me a joke'",
    )

    assert service.integration_id == integration.id
    assert service.ai_generative_ai_type == "openai"
    assert service.ai_generative_ai_model == "gpt-4"
    assert service.ai_output_type == "text"
    assert service.ai_prompt == {
        "mode": "simple",
        "formula": "'Tell me a joke'",
        "version": "0.1",
    }
    assert service.ai_choices == []
    assert service.ai_temperature is None


@pytest.mark.django_db
def test_ai_agent_service_creation_with_temperature(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_temperature=0.7,
        ai_prompt="'Be creative'",
    )

    assert service.ai_temperature == 0.7


@pytest.mark.django_db
def test_ai_agent_service_creation_with_choices(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="choice",
        ai_prompt="'Categorize: positive or negative'",
        ai_choices=["positive", "negative", "neutral"],
    )

    assert service.ai_output_type == "choice"
    assert service.ai_choices == ["positive", "negative", "neutral"]


@pytest.mark.django_db
def test_ai_agent_service_update(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4", "gpt-3.5-turbo"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'Original prompt'",
    )

    service_type = service.get_type()
    ServiceHandler().update_service(
        service_type,
        service,
        ai_generative_ai_model="gpt-3.5-turbo",
        ai_prompt="'Updated prompt'",
        ai_temperature=0.5,
    )

    service.refresh_from_db()

    assert service.ai_generative_ai_model == "gpt-3.5-turbo"
    assert service.ai_prompt["formula"] == "'Updated prompt'"
    assert service.ai_temperature == 0.5


@pytest.mark.django_db
def test_ai_agent_service_dispatch_text_output(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'Tell me a joke'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with mock_ai_prompt(return_value="Why did the chicken cross the road?"):
        result = service_type.dispatch(service, dispatch_context)

    assert result.data == {"result": "Why did the chicken cross the road?"}


@pytest.mark.django_db
def test_ai_agent_service_dispatch_with_temperature(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_temperature=0.3,
        ai_prompt="'Be precise'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with patch(
        "baserow.core.generative_ai.generative_ai_model_types.OpenAIGenerativeAIModelType.prompt"
    ) as mock_prompt:
        mock_prompt.return_value = "Precise response"
        service_type.dispatch(service, dispatch_context)

        mock_prompt.assert_called_once()
        call_kwargs = mock_prompt.call_args[1]
        assert call_kwargs["temperature"] == 0.3


@pytest.mark.django_db
def test_ai_agent_service_dispatch_choice_output(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="choice",
        ai_prompt="'Is this positive or negative: I love this!'",
        ai_choices=["positive", "negative", "neutral"],
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with mock_ai_prompt(return_value="positive"):
        result = service_type.dispatch(service, dispatch_context)

    assert result.data == {"result": "positive"}


@pytest.mark.django_db
def test_ai_agent_service_dispatch_with_formula(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="concat('Summarize this text: ', get('text'))",
    )

    service_type = service.get_type()

    formula_context = {"text": "This is a long article about AI technology..."}
    dispatch_context = FakeDispatchContext(context=formula_context)

    with mock_ai_prompt(return_value="Summary: AI technology article"):
        result = service_type.dispatch(service, dispatch_context)

    assert result.data == {"result": "Summary: AI technology article"}


@pytest.mark.django_db
def test_ai_agent_service_dispatch_missing_provider(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'Test'",
    )

    service.ai_generative_ai_type = ""
    service.save()

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service_type.dispatch(service, dispatch_context)

    assert "AI provider type is missing" in str(exc_info.value)


@pytest.mark.django_db
def test_ai_agent_service_dispatch_missing_model(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'Test'",
    )

    # Clear model
    service.ai_generative_ai_model = ""
    service.save()

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service_type.dispatch(service, dispatch_context)

    assert "AI model is missing" in str(exc_info.value)


@pytest.mark.django_db
def test_ai_agent_service_dispatch_missing_choices(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="choice",
        ai_prompt="'Categorize this'",
        ai_choices=[],  # Empty choices
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        service_type.dispatch(service, dispatch_context)

    assert "choice is required" in str(exc_info.value)


@pytest.mark.django_db
def test_ai_agent_service_dispatch_ai_error(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'Test'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(UnexpectedDispatchException) as exc_info:
        with mock_ai_prompt(should_fail=True):
            service_type.dispatch(service, dispatch_context)

    assert "AI prompt execution failed" in str(exc_info.value)


@pytest.mark.django_db
def test_ai_agent_service_dispatch_with_integration_settings(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-env-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-3.5-turbo"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()

    # Create integration with custom OpenAI settings
    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={
            "openai": {
                "api_key": "sk-integration-key",
                "models": ["gpt-4"],
                "organization": "org-integration",
            }
        },
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'Test'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with patch(
        "baserow.core.generative_ai.generative_ai_model_types.OpenAIGenerativeAIModelType.prompt"
    ) as mock_prompt:
        mock_prompt.return_value = "Response"
        service_type.dispatch(service, dispatch_context)

        mock_prompt.assert_called_once()
        call_kwargs = mock_prompt.call_args[1]
        assert "settings_override" in call_kwargs
        assert call_kwargs["settings_override"]["api_key"] == "sk-integration-key"


@pytest.mark.django_db
def test_ai_agent_service_generate_schema(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'Test'",
    )

    service_type = service.get_type()
    schema = service_type.generate_schema(service)

    assert schema == {
        "type": "object",
        "title": f"Service{service.id}Schema",  # Uses base ServiceType schema naming
        "properties": {
            "result": {
                "type": "string",
                "title": "AI Response",
            }
        },
    }


@pytest.mark.django_db
def test_ai_agent_service_export_import(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(user, integration_type, application=application)
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="choice",
        ai_temperature=0.5,
        ai_prompt="'Categorize sentiment'",
        ai_choices=["positive", "negative", "neutral"],
    )

    service_type = service.get_type()

    serialized = json.loads(json.dumps(service_type.export_serialized(service)))
    expected_serialized = {
        "id": AnyInt(),
        "integration_id": integration.id,
        "sample_data": None,
        "type": "ai_agent",
        "ai_generative_ai_type": "openai",
        "ai_generative_ai_model": "gpt-4",
        "ai_output_type": "choice",
        "ai_temperature": 0.5,
        "ai_prompt": {
            "formula": "'Categorize sentiment'",
            "mode": "simple",
            "version": "0.1",
        },
        "ai_choices": ["positive", "negative", "neutral"],
    }
    assert serialized == expected_serialized

    new_service = service_type.import_serialized(
        None, serialized, {integration.id: integration}, lambda x, d: x
    )
    assert new_service.ai_generative_ai_type == "openai"
    assert new_service.ai_generative_ai_model == "gpt-4"
    assert new_service.ai_output_type == "choice"
    assert new_service.ai_temperature == 0.5
    assert new_service.ai_prompt["formula"] == "'Categorize sentiment'"
    assert new_service.ai_choices == ["positive", "negative", "neutral"]


@pytest.mark.django_db
def test_ai_agent_service_dispatch_in_published_workflow(data_fixture, settings):
    """
    Test that AI agent services work correctly when a workflow is published.
    When published, the workflow is copied and workspace relationships may be null.
    This test verifies that the integration settings are properly copied.
    """

    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    workspace.generative_ai_models_settings = {
        "openai": {"api_key": "sk-workspace-key", "models": ["gpt-4"]}
    }
    workspace.save()

    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(automation=automation)

    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(
            user,
            integration_type,
            application=automation,
            ai_settings={
                "openai": {"api_key": "sk-integration-key", "models": ["gpt-4"]}
            },
        )
        .specific
    )

    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'What is 2+2?'",
    )

    node_type = automation_node_type_registry.get("ai_agent")
    action_node = AutomationNodeHandler().create_node(
        user=user,
        workflow=workflow,
        node_type=node_type,
        service=service,
    )

    published_workflow = AutomationWorkflowHandler().publish(workflow)
    published_action_node = published_workflow.automation_workflow_nodes.filter(
        content_type__model="aiagentactionnode"
    ).first()
    published_service = published_action_node.service.specific
    published_integration = published_service.integration.specific

    # Verify the integration settings were properly copied
    assert published_integration.ai_settings == {
        "openai": {"api_key": "sk-integration-key", "models": ["gpt-4"]}
    }

    # Verify the integration type can get the provider settings
    published_integration_type = AIIntegrationType()
    provider_settings = published_integration_type.get_provider_settings(
        published_integration, "openai"
    )
    assert provider_settings["api_key"] == "sk-integration-key"
    assert provider_settings["models"] == ["gpt-4"]

    # Dispatch the service in the published workflow context
    service_type = published_service.get_type()
    dispatch_context = FakeDispatchContext()

    with mock_ai_prompt(return_value="4"):
        result = service_type.dispatch(published_service, dispatch_context)

    assert result.data == {"result": "4"}


@pytest.mark.django_db
def test_ai_agent_service_requires_integration_settings_not_workspace_fallback(
    data_fixture, settings
):
    """
    Test that demonstrates AI integrations must have explicit settings,
    not rely on workspace fallback, because published workflows have workspace=None.
    """

    settings.BASEROW_OPENAI_API_KEY = "sk-test"
    settings.BASEROW_OPENAI_MODELS = ["gpt-4"]

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    workspace.generative_ai_models_settings = {
        "openai": {"api_key": "sk-workspace-key", "models": ["gpt-4"]}
    }
    workspace.save()

    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    workflow = data_fixture.create_automation_workflow(automation=automation)

    # Create AI integration WITHOUT settings (relies on workspace fallback)
    integration_type = AIIntegrationType()
    integration = (
        IntegrationService()
        .create_integration(
            user,
            integration_type,
            application=automation,
            ai_settings={},  # Empty - relies on workspace settings
        )
        .specific
    )

    # Before publishing, integration can access workspace settings
    provider_settings = integration_type.get_provider_settings(integration, "openai")
    assert provider_settings["api_key"] == "sk-workspace-key"

    # Create AI agent service
    service = ServiceHandler().create_service(
        AIAgentServiceType(),
        integration_id=integration.id,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4",
        ai_output_type="text",
        ai_prompt="'What is 2+2?'",
    )

    node_type = automation_node_type_registry.get("ai_agent")
    action_node = AutomationNodeHandler().create_node(
        user=user,
        workflow=workflow,
        node_type=node_type,
        service=service,
    )

    published_workflow = AutomationWorkflowHandler().publish(workflow)

    published_action_node = published_workflow.automation_workflow_nodes.filter(
        content_type__model="aiagentactionnode"
    ).first()
    published_service = published_action_node.service.specific
    published_integration = published_service.integration.specific

    # Verify workspace is None in published automation
    assert published_integration.application.workspace is None

    # After publishing, verify workspace settings were materialized into integration
    assert published_integration.ai_settings == {
        "openai": {"api_key": "sk-workspace-key", "models": ["gpt-4"]}
    }

    # After publishing, integration should still have access to settings
    provider_settings = integration_type.get_provider_settings(
        published_integration, "openai"
    )
    # Settings should be available because they were materialized during export
    assert provider_settings["api_key"] == "sk-workspace-key"
    assert provider_settings["models"] == ["gpt-4"]
