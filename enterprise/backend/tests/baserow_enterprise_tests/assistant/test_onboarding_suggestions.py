from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)

from baserow_enterprise.assistant.exceptions import AssistantModelNotSupportedError
from baserow_enterprise.assistant.onboarding import (
    OnboardingPromptSuggestion,
    OnboardingPromptSuggestions,
    generate_onboarding_prompt_suggestions,
)

URL = reverse("assistant:onboarding_prompt_suggestions")


def make_run_sync_mock(mocker, amount=4):
    result = mocker.MagicMock()
    result.output = OnboardingPromptSuggestions(
        suggestions=[
            OnboardingPromptSuggestion(name=f"Name {i}", prompt=f"Prompt {i}")
            for i in range(amount)
        ]
    )
    return mocker.patch(
        "baserow_enterprise.assistant.onboarding.onboarding_suggestions_agent.run_sync",
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
    mocker.patch(
        "baserow_enterprise.assistant.onboarding.get_model_string",
        return_value="openai:gpt-4o",
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

    user_prompt = run_sync.call_args.args[0]
    assert "Marketing" in user_prompt
    assert "Client services" in user_prompt


@pytest.mark.django_db
def test_suggestions_falls_back_to_the_profile_language(
    api_client, data_fixture, mocker
):
    _, token = data_fixture.create_user_and_token(language="fr")
    mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
        return_value=None,
    )
    mocker.patch(
        "baserow_enterprise.assistant.onboarding.get_model_string",
        return_value="openai:gpt-4o",
    )
    run_sync = make_run_sync_mock(mocker)

    api_client.post(URL, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    assert "'fr'" in run_sync.call_args.args[0]


@pytest.mark.django_db
def test_suggestions_language_overrides_the_profile_language(
    api_client, data_fixture, mocker
):
    _, token = data_fixture.create_user_and_token(language="fr")
    mocker.patch(
        "baserow_enterprise.api.assistant.views.check_lm_ready_or_raise",
        return_value=None,
    )
    mocker.patch(
        "baserow_enterprise.assistant.onboarding.get_model_string",
        return_value="openai:gpt-4o",
    )
    run_sync = make_run_sync_mock(mocker)

    api_client.post(
        URL, {"language": "nl"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert "'nl'" in run_sync.call_args.args[0]


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
def test_generate_returns_at_most_the_requested_amount(mocker):
    mocker.patch(
        "baserow_enterprise.assistant.onboarding.get_model_string",
        return_value="openai:gpt-4o",
    )
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
