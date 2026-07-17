from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.cache import local_cache
from baserow.core.generative_ai.generative_ai_model_types import (
    OpenAIGenerativeAIModelType,
)


@pytest.mark.django_db
def test_database_provider_is_ignored_while_feature_flag_is_disabled(settings):
    settings.FEATURE_FLAGS = []
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )

    model_type = OpenAIGenerativeAIModelType()
    assert model_type.get_api_key() == "environment-key"
    assert model_type.get_enabled_models() == ["environment-model"]


@pytest.mark.django_db
def test_database_provider_is_authoritative_when_enabled(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )
    AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="disabled-model",
        is_enabled=False,
    )

    model_type = OpenAIGenerativeAIModelType()
    assert model_type.get_api_key() == "database-key"
    assert model_type.get_enabled_models() == ["database-model"]

    provider.api_key = ""
    provider.is_active = False
    provider.save(update_fields=("api_key", "is_active"))
    local_cache.clear()
    assert model_type.get_api_key() is None
    assert model_type.get_enabled_models() == []


@pytest.mark.django_db
def test_database_provider_resolution_is_cached_per_request(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )
    model_type = OpenAIGenerativeAIModelType()

    with local_cache.context(), CaptureQueriesContext(connection) as queries:
        assert model_type.get_api_key() == "database-key"
        assert model_type.get_enabled_models() == ["database-model"]
        assert model_type.get_api_key() == "database-key"

    assert len(queries) == 2


@pytest.mark.django_db
def test_existing_workspace_and_automation_settings_keep_precedence(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )
    workspace = data_fixture.create_workspace()
    workspace.generative_ai_models_settings = {
        "openai": {
            "api_key": "workspace-key",
            "models": ["workspace-model"],
        }
    }
    workspace.save(update_fields=("generative_ai_models_settings",))

    model_type = OpenAIGenerativeAIModelType()
    assert model_type.get_api_key(workspace) == "workspace-key"
    assert model_type.get_enabled_models(workspace) == ["workspace-model"]
    assert (
        model_type.get_api_key(
            workspace, settings_override={"api_key": "automation-key"}
        )
        == "automation-key"
    )


@pytest.mark.django_db
def test_environment_remains_fallback_when_database_provider_is_missing(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]

    model_type = OpenAIGenerativeAIModelType()
    assert model_type.get_api_key() == "environment-key"
    assert model_type.get_enabled_models() == ["environment-model"]
