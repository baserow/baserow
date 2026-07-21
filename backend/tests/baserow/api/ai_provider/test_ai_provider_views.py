from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel


@pytest.fixture
def enabled_ai_providers(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]


@pytest.fixture
def staff_headers(data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    return {"HTTP_AUTHORIZATION": f"JWT {token}"}


@pytest.mark.django_db
def test_ai_provider_api_is_feature_gated_and_staff_only(
    api_client, data_fixture, settings, enabled_ai_providers
):
    _, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:ai_provider:list"), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    _, staff_token = data_fixture.create_user_and_token(is_staff=True)
    settings.FEATURE_FLAGS = []
    response = api_client.get(
        reverse("api:ai_provider:list"),
        HTTP_AUTHORIZATION=f"JWT {staff_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"


@pytest.mark.django_db
def test_provider_crud_never_returns_api_key(
    api_client, staff_headers, enabled_ai_providers
):
    response = api_client.post(
        reverse("api:ai_provider:list"),
        {
            "provider_type": "openai",
            "api_key": "secret-key",
            "extra_settings": {"organization": "org-1"},
            "models": [{"model_identifier": "gpt-4o"}],
        },
        format="json",
        **staff_headers,
    )

    assert response.status_code == HTTP_201_CREATED
    assert response.json() == {
        "id": response.json()["id"],
        "provider_type": "openai",
        "extra_settings": {"organization": "org-1"},
        "is_active": True,
        "models": [
            {
                "id": response.json()["models"][0]["id"],
                "model_identifier": "gpt-4o",
                "is_enabled": True,
                "last_test_at": None,
                "last_test_status": None,
                "last_test_error": "",
            }
        ],
    }
    provider = AIProviderConfig.objects.get()
    assert provider.api_key == "secret-key"

    response = api_client.patch(
        reverse("api:ai_provider:item", kwargs={"provider_id": provider.id}),
        {"is_active": False},
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["is_active"] is False
    assert "api_key" not in response.json()

    response = api_client.patch(
        reverse("api:ai_provider:item", kwargs={"provider_id": provider.id}),
        {"api_key": ""},
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    provider.refresh_from_db()
    assert provider.api_key == "secret-key"

    response = api_client.delete(
        reverse("api:ai_provider:item", kwargs={"provider_id": provider.id}),
        **staff_headers,
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert not AIProviderConfig.objects.exists()


@pytest.mark.django_db
def test_provider_connection_settings_are_required(
    api_client, staff_headers, enabled_ai_providers
):
    url = reverse("api:ai_provider:list")
    response = api_client.post(
        url,
        {"provider_type": "openai"},
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "api_key" in response.json()["detail"]

    response = api_client.post(
        url,
        {"provider_type": "ollama"},
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "host" in response.json()["detail"]

    response = api_client.post(
        url,
        {
            "provider_type": "ollama",
            "extra_settings": {"host": "http://ollama:11434"},
        },
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_201_CREATED


@pytest.mark.django_db
def test_blank_optional_provider_settings_are_not_stored(
    api_client, staff_headers, enabled_ai_providers
):
    response = api_client.post(
        reverse("api:ai_provider:list"),
        {
            "provider_type": "openai",
            "api_key": "secret",
            "extra_settings": {"organization": "", "base_url": ""},
        },
        format="json",
        **staff_headers,
    )

    assert response.status_code == HTTP_201_CREATED
    assert response.json()["extra_settings"] == {}
    assert AIProviderConfig.objects.get().extra_settings == {}


@pytest.mark.django_db
def test_provider_type_metadata_marks_required_connection_settings(
    api_client, staff_headers, enabled_ai_providers
):
    response = api_client.get(reverse("api:ai_provider:types"), **staff_headers)

    assert response.status_code == HTTP_200_OK
    provider_types = {item["type"]: item for item in response.json()}
    assert provider_types["openai"]["uses_api_key"] is True
    assert provider_types["ollama"]["uses_api_key"] is False
    assert provider_types["ollama"]["extra_fields"] == [
        {"name": "host", "required": True, "allow_blank": False}
    ]


@pytest.mark.django_db
def test_provider_and_model_uniqueness_errors_are_mapped(
    api_client, staff_headers, enabled_ai_providers
):
    url = reverse("api:ai_provider:list")
    payload = {
        "provider_type": "anthropic",
        "api_key": "secret",
        "models": [{"model_identifier": "claude-sonnet"}],
    }

    assert (
        api_client.post(url, payload, format="json", **staff_headers).status_code == 201
    )
    response = api_client.post(url, payload, format="json", **staff_headers)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED"

    provider = AIProviderConfig.objects.get()
    response = api_client.post(
        reverse("api:ai_provider:create_model", kwargs={"provider_id": provider.id}),
        {"model_identifier": "claude-sonnet"},
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED"


@pytest.mark.django_db
def test_models_can_be_created_updated_disabled_and_deleted(
    api_client, staff_headers, enabled_ai_providers
):
    provider = AIProviderConfig.objects.create(
        provider_type="mistral", api_key="secret"
    )
    response = api_client.post(
        reverse("api:ai_provider:create_model", kwargs={"provider_id": provider.id}),
        {"model_identifier": "mistral-large"},
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_201_CREATED
    model_id = response.json()["id"]

    response = api_client.patch(
        reverse("api:ai_provider:model_item", kwargs={"model_id": model_id}),
        {"model_identifier": "mistral-small", "is_enabled": False},
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["model_identifier"] == "mistral-small"
    assert response.json()["is_enabled"] is False

    response = api_client.delete(
        reverse("api:ai_provider:model_item", kwargs={"model_id": model_id}),
        **staff_headers,
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert not AIProviderModel.objects.exists()


@pytest.mark.django_db
def test_saved_models_are_tested_in_one_request_and_results_are_persisted(
    api_client, staff_headers, enabled_ai_providers
):
    provider = AIProviderConfig.objects.create(
        provider_type="mistral", api_key="never-return-this"
    )
    first = AIProviderModel.objects.create(
        provider_config=provider, model_identifier="mistral-large"
    )
    second = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="mistral-small",
        is_enabled=False,
    )

    with patch(
        "baserow.core.generative_ai.generative_ai_model_types."
        "MistralGenerativeAIModelType.prompt",
        side_effect=[None, Exception("bad credential never-return-this")],
    ) as prompt:
        response = api_client.post(
            reverse("api:ai_provider:test_models"),
            {"model_ids": [first.id, second.id]},
            format="json",
            **staff_headers,
        )

    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    assert [result["model_id"] for result in results] == [first.id, second.id]
    assert [result["status"] for result in results] == ["success", "failure"]
    assert results[1]["error"] == "bad credential [redacted]"
    assert "never-return-this" not in response.content.decode()
    assert prompt.call_count == 2
    prompt.assert_any_call(
        "mistral-small",
        "OK",
        settings_override={
            "api_key": "never-return-this",
            "models": ["mistral-large", "mistral-small"],
        },
        model_settings_override={"max_tokens": 16},
    )
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.last_test_status == "success"
    assert second.last_test_status == "failure"


@pytest.mark.django_db
def test_a_single_saved_model_uses_the_same_test_endpoint(
    api_client, staff_headers, enabled_ai_providers
):
    provider = AIProviderConfig.objects.create(
        provider_type="mistral", api_key="secret"
    )
    model = AIProviderModel.objects.create(
        provider_config=provider, model_identifier="mistral-large"
    )

    with patch(
        "baserow.core.generative_ai.generative_ai_model_types."
        "MistralGenerativeAIModelType.prompt"
    ):
        response = api_client.post(
            reverse("api:ai_provider:test_models"),
            {"model_ids": [model.id]},
            format="json",
            **staff_headers,
        )

    assert response.status_code == HTTP_200_OK
    assert response.json()["results"][0]["model_id"] == model.id
    assert response.json()["results"][0]["status"] == "success"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"model_ids": []},
        {"model_ids": [1, 1]},
    ],
)
def test_model_test_request_validation(
    api_client, staff_headers, enabled_ai_providers, payload
):
    response = api_client.post(
        reverse("api:ai_provider:test_models"),
        payload,
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_testing_an_unknown_saved_model_returns_not_found(
    api_client, staff_headers, enabled_ai_providers
):
    response = api_client.post(
        reverse("api:ai_provider:test_models"),
        {"model_ids": [999999]},
        format="json",
        **staff_headers,
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_AI_PROVIDER_MODEL_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("provider_type", "expected_model"),
    [
        ("openai", "gpt-5"),
        ("anthropic", "claude-sonnet-4-5"),
        ("mistral", "mistral-large-latest"),
    ],
)
def test_model_discovery_returns_pydantic_ai_known_models(
    api_client,
    staff_headers,
    enabled_ai_providers,
    provider_type,
    expected_model,
):
    response = api_client.get(
        reverse("api:ai_provider:discover_models"),
        {"provider_type": provider_type},
        **staff_headers,
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["supported"] is True
    assert expected_model in response.json()["models"]


@pytest.mark.django_db
def test_model_discovery_handles_unsupported_catalogs_and_types(
    api_client, staff_headers, enabled_ai_providers
):
    url = reverse("api:ai_provider:discover_models")
    response = api_client.get(url, {"provider_type": "ollama"}, **staff_headers)
    assert response.status_code == HTTP_200_OK
    assert response.json() == {"models": [], "supported": False}

    response = api_client.get(url, {"provider_type": "unknown"}, **staff_headers)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AI_PROVIDER_TYPE_NOT_SUPPORTED"
