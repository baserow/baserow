import pytest

from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.ai_provider.registries import (
    ai_provider_model_feature_type_registry,
)


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
