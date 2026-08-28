import pytest

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_MODEL,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow_enterprise.assistant import model_profiles as model_profiles_module
from baserow_enterprise.assistant.model_profiles import (
    ORCHESTRATOR,
    SAMPLE,
    SUBAGENT,
    get_model_settings,
    resolve_assistant_model,
)


@pytest.mark.parametrize("model", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
@pytest.mark.parametrize("role", [ORCHESTRATOR, SUBAGENT, SAMPLE])
def test_groq_gpt_oss_profiles_do_not_send_unsupported_reasoning_format(model, role):
    model_settings = get_model_settings(f"groq:{model}", role)

    assert "groq_reasoning_format" not in model_settings


@pytest.mark.parametrize("role", [ORCHESTRATOR, SUBAGENT, SAMPLE])
@pytest.mark.parametrize(
    "model", ["google:gemini-3.6-flash", "google:gemini-3.7-flash"]
)
def test_current_google_profiles_do_not_send_unsupported_sampling_settings(model, role):
    model_settings = get_model_settings(model, role)

    assert "temperature" not in model_settings
    assert "top_p" not in model_settings
    assert "top_k" not in model_settings


def test_older_google_profiles_keep_supported_sampling_settings():
    model_settings = get_model_settings("google:gemini-2.5-flash", ORCHESTRATOR)

    assert "temperature" in model_settings


@pytest.mark.django_db
def test_resolved_profile_loads_provider_state_once_and_is_query_free_afterward(
    data_fixture,
    django_assert_num_queries,
    mocker,
    settings,
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    workspace = data_fixture.create_workspace()
    provider = AIProviderHandler.create_provider(
        "openai",
        workspace=workspace,
        api_key="snapshot-key",
        models_data=[
            {
                "model_identifier": "snapshot-model",
                "feature_types": [AI_PROVIDER_FEATURE_KUMA],
            }
        ],
    )
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        workspace=workspace,
        model=provider.models.get(),
    )
    state_loader = mocker.spy(model_profiles_module, "get_ai_provider_state")

    model_profile = resolve_assistant_model(workspace=workspace)

    assert state_loader.call_count == 1
    with django_assert_num_queries(0):
        assert model_profile.model_string == "openai:snapshot-model"
        assert model_profile.get_settings(ORCHESTRATOR)
        model = model_profile.create_model()
        assert model.wrapped.system == "openai"


@pytest.mark.django_db
def test_resolved_profile_does_not_change_when_persisted_selection_changes(
    data_fixture,
    settings,
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    workspace = data_fixture.create_workspace()
    first_provider = AIProviderHandler.create_provider(
        "openai",
        workspace=workspace,
        api_key="first-key",
        models_data=[
            {
                "model_identifier": "first-model",
                "feature_types": [AI_PROVIDER_FEATURE_KUMA],
            }
        ],
    )
    second_provider = AIProviderHandler.create_provider(
        "anthropic",
        workspace=workspace,
        api_key="second-key",
        models_data=[
            {
                "model_identifier": "second-model",
                "feature_types": [AI_PROVIDER_FEATURE_KUMA],
            }
        ],
    )
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        workspace=workspace,
        model=first_provider.models.get(),
    )
    model_profile = resolve_assistant_model(workspace=workspace)

    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        workspace=workspace,
        model=second_provider.models.get(),
    )

    assert model_profile.model_string == "openai:first-model"
    resolved_model = model_profile.create_model().wrapped
    assert resolved_model.system == "openai"
    assert resolved_model._provider.client.api_key == "first-key"


def test_explicit_model_profile_does_not_load_persisted_provider_state(mocker):
    state_loader = mocker.patch(
        "baserow_enterprise.assistant.model_profiles.get_ai_provider_state"
    )

    model_profile = resolve_assistant_model(model="google-gla:gemini-test")

    assert model_profile.model_string == "google:gemini-test"
    assert model_profile.source == "explicit"
    state_loader.assert_not_called()
