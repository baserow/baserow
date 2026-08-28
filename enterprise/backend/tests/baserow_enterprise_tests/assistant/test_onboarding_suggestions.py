from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow_enterprise.assistant.exceptions import (
    AssistantConfiguredModelNotAvailableError,
    AssistantModelNotSupportedError,
)
from baserow_enterprise.assistant.onboarding import (
    OnboardingPromptSuggestion,
    OnboardingPromptSuggestions,
    generate_onboarding_prompt_suggestions,
)

URL = reverse("assistant:onboarding_prompt_suggestions")


def make_run_sync_mock(mocker, amount=4):
    model_profile = mocker.MagicMock()
    model_profile.create_model.return_value = mocker.sentinel.assistant_model
    mocker.patch(
        "baserow_enterprise.assistant.onboarding.resolve_assistant_model",
        return_value=model_profile,
    )
    mocker.patch(
        "baserow_enterprise.api.assistant.views.resolve_assistant_model",
        return_value=model_profile,
    )
    result = mocker.MagicMock()
    result.output = OnboardingPromptSuggestions(
        suggestions=[
            OnboardingPromptSuggestion(name=f"Name {i}", prompt=f"Prompt {i}")
            for i in range(amount)
        ]
    )
    return mocker.patch(
        "baserow_enterprise.assistant.onboarding.run_agent_sync_with_model",
        return_value=result,
    )


@pytest.mark.django_db
def test_suggestions_requires_authentication(api_client):
    response = api_client.post(URL, {}, format="json")
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_suggestions_returns_the_generated_suggestions(
    api_client, data_fixture, mocker
):
    _, token = data_fixture.create_user_and_token()
    mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
        return_value=None,
    )
    run_sync = make_run_sync_mock(mocker)

    response = api_client.post(
        URL,
        {"industry": "Marketing", "team": "Client services"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    suggestions = response.json()["suggestions"]
    assert len(suggestions) == 4
    assert suggestions[0] == {"name": "Name 0", "prompt": "Prompt 0"}

    assert run_sync.call_args.args[0] is not None
    user_prompt = run_sync.call_args.args[1]
    assert "Marketing" in user_prompt
    assert "Client services" in user_prompt
    assert run_sync.call_args.kwargs["model"] is mocker.sentinel.assistant_model


@pytest.mark.django_db
def test_suggestions_falls_back_to_the_profile_language(
    api_client, data_fixture, mocker
):
    _, token = data_fixture.create_user_and_token(language="fr")
    mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
        return_value=None,
    )
    run_sync = make_run_sync_mock(mocker)

    api_client.post(URL, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    assert "'fr'" in run_sync.call_args.args[1]


@pytest.mark.django_db
def test_suggestions_language_overrides_the_profile_language(
    api_client, data_fixture, mocker
):
    _, token = data_fixture.create_user_and_token(language="fr")
    mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
        return_value=None,
    )
    run_sync = make_run_sync_mock(mocker)

    api_client.post(
        URL, {"language": "nl"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert "'nl'" in run_sync.call_args.args[1]


@pytest.mark.django_db
def test_suggestions_errors_when_the_model_is_not_supported(
    api_client, data_fixture, mocker
):
    _, token = data_fixture.create_user_and_token()
    mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
        side_effect=AssistantModelNotSupportedError("nope"),
    )

    response = api_client.post(
        URL, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ASSISTANT_MODEL_NOT_SUPPORTED"


@pytest.mark.django_db
def test_suggestions_reports_a_database_configured_model_failure(
    api_client, data_fixture, mocker
):
    _, token = data_fixture.create_user_and_token()
    mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
        side_effect=AssistantConfiguredModelNotAvailableError("database model failed"),
    )

    response = api_client.post(
        URL, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == (
        "ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE"
    )


@pytest.mark.django_db
def test_suggestions_reports_that_kuma_is_disabled(api_client, data_fixture, settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    _, token = data_fixture.create_user_and_token()
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_DISABLED,
    )

    response = api_client.post(
        URL, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ASSISTANT_MODEL_DISABLED"


@pytest.mark.django_db
def test_generate_returns_at_most_the_requested_amount(mocker):
    make_run_sync_mock(mocker, amount=15)

    suggestions = generate_onboarding_prompt_suggestions("Marketing", "Ops", "en")

    assert len(suggestions) == 4


@pytest.mark.django_db
def test_suggestions_rejects_long_answers(api_client, data_fixture, mocker):
    _, token = data_fixture.create_user_and_token()
    mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
        return_value=None,
    )

    response = api_client.post(
        URL,
        {"industry": "a" * 49, "team": "b" * 49},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    detail = response.json()["detail"]
    assert "industry" in detail
    assert "team" in detail
