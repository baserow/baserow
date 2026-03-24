from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig


@pytest.mark.django_db
def test_list_instance_providers_unauthenticated(api_client):
    response = api_client.get(reverse("api:ai_providers:list") + "?scope=instance")
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_list_instance_providers_non_staff(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    response = api_client.get(
        reverse("api:ai_providers:list") + "?scope=instance",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_list_instance_providers_staff(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI Test",
        scope_type="instance",
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_field"]},
        ],
    )

    response = api_client.get(
        reverse("api:ai_providers:list") + "?scope=instance",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "OpenAI Test"
    assert data[0]["provider_type"] == "openai"
    assert len(data[0]["models"]) == 1
    assert data[0]["models"][0]["model_identifier"] == "gpt-4o"
    assert data[0]["models"][0]["features"] == ["ai_field"]


@pytest.mark.django_db
def test_create_instance_provider(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:ai_providers:list") + "?scope=instance",
        {
            "provider_type": "anthropic",
            "name": "Anthropic Test",
            "api_key": "sk-ant-test",
            "models_data": [
                {
                    "model_identifier": "claude-sonnet-4-20250514",
                    "features": ["ai_field", "ai_assistant"],
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["provider_type"] == "anthropic"
    assert data["name"] == "Anthropic Test"
    # API key is never returned
    assert data["api_key"] == ""
    assert data["has_api_key"] is True
    assert len(data["models"]) == 1
    assert set(data["models"][0]["features"]) == {"ai_field", "ai_assistant"}
    assert AIProviderConfig.objects.filter(id=data["id"]).exists()


@pytest.mark.django_db
def test_create_instance_provider_non_staff(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    response = api_client.post(
        reverse("api:ai_providers:list") + "?scope=instance",
        {
            "provider_type": "openai",
            "name": "Test",
            "api_key": "sk-test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_get_single_provider(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Test",
        scope_type="instance",
    )

    response = api_client.get(
        reverse("api:ai_providers:item", kwargs={"provider_id": provider.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "Test"


@pytest.mark.django_db
def test_get_nonexistent_provider(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    response = api_client.get(
        reverse("api:ai_providers:item", kwargs={"provider_id": 99999}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_provider(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Old",
        scope_type="instance",
    )

    response = api_client.patch(
        reverse("api:ai_providers:item", kwargs={"provider_id": provider.id}),
        {"name": "New"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "New"


@pytest.mark.django_db
def test_delete_provider(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Test",
        scope_type="instance",
    )

    response = api_client.delete(
        reverse("api:ai_providers:item", kwargs={"provider_id": provider.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert not AIProviderConfig.objects.filter(id=provider.id).exists()


@pytest.mark.django_db
def test_list_workspace_effective_providers(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Instance OpenAI",
        scope_type="instance",
        api_key="sk-secret",
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_field"]},
        ],
    )
    AIProviderHandler.create_provider(
        user=user,
        provider_type="anthropic",
        name="WS Anthropic",
        scope_type="workspace",
        scope_id=workspace.id,
        api_key="sk-ws-key",
    )

    response = api_client.get(
        reverse("api:ai_providers:list") + f"?scope=workspace&scope_id={workspace.id}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert len(data) == 2

    inherited = [p for p in data if not p["is_own_scope"]]
    own = [p for p in data if p["is_own_scope"]]

    # Inherited provider — API key never exposed
    assert len(inherited) == 1
    assert inherited[0]["name"] == "Instance OpenAI"
    assert inherited[0]["api_key"] == ""
    assert inherited[0]["has_api_key"] is True

    # Own provider — API key also never exposed, but has_api_key is True
    assert len(own) == 1
    assert own[0]["name"] == "WS Anthropic"
    assert own[0]["api_key"] == ""
    assert own[0]["has_api_key"] is True


@pytest.mark.django_db
def test_toggle_override(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Instance",
        scope_type="instance",
    )

    response = api_client.patch(
        reverse("api:ai_providers:override", kwargs={"provider_id": provider.id})
        + f"?scope=workspace&scope_id={workspace.id}",
        {"is_enabled": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["is_enabled"] is False


@pytest.mark.django_db
def test_available_models(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI",
        scope_type="instance",
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_field"]},
            {"model_identifier": "gpt-4o-mini", "features": ["ai_assistant"]},
        ],
    )

    response = api_client.get(
        reverse("api:ai_providers:available_models")
        + "?feature=ai_field&scope=instance",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["model_identifier"] == "gpt-4o"


@pytest.mark.django_db
def test_feature_defaults_crud(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(is_staff=True)

    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI",
        scope_type="instance",
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_assistant"]},
        ],
    )
    model = provider.models.first()

    # GET - no defaults yet
    response = api_client.get(
        reverse("api:ai_providers:feature_defaults") + "?scope=instance",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == []

    # SET default
    response = api_client.patch(
        reverse("api:ai_providers:feature_defaults") + "?scope=instance",
        {"feature_type": "ai_assistant", "provider_model_id": model.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # GET - now has a default
    response = api_client.get(
        reverse("api:ai_providers:feature_defaults") + "?scope=instance",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["feature_type"] == "ai_assistant"
    assert data[0]["provider_model_id"] == model.id


@pytest.mark.django_db
def test_missing_scope_param(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    response = api_client.get(
        reverse("api:ai_providers:list"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
