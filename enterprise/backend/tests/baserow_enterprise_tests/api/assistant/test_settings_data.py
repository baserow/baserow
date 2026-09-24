from django.shortcuts import reverse

import pytest

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
    AI_PROVIDER_FEATURE_MODE_MODEL,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel


@pytest.mark.django_db
def test_public_settings_expose_database_kuma_availability(api_client, settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="database-model",
        feature_types=[AI_PROVIDER_FEATURE_KUMA],
    )
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        model=model,
    )

    response = api_client.get(reverse("api:settings:get"))

    assert response.status_code == 200
    assert response.json()["kuma"] == {"is_enabled": True}


@pytest.mark.django_db
def test_public_settings_respect_explicit_kuma_disable(api_client, settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq:legacy-model"
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_DISABLED,
    )

    response = api_client.get(reverse("api:settings:get"))

    assert response.status_code == 200
    assert response.json()["kuma"] == {"is_enabled": False}
