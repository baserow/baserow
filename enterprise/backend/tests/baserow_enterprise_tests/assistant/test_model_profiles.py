import pytest
from pydantic import BaseModel
from pydantic_ai import NativeOutput

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_AI_FIELDS,
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
    AI_PROVIDER_FEATURE_MODE_MODEL,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.models import Workspace
from baserow_enterprise.assistant import model_profiles as model_profiles_module
from baserow_enterprise.assistant.exceptions import AssistantModelDisabledError
from baserow_enterprise.assistant.model_profiles import (
    DOCUMENTATION,
    ORCHESTRATOR,
    SAMPLE,
    SUBAGENT,
    SUGGESTIONS,
    TITLE,
    UTILITY,
    get_model_settings,
    resolve_assistant_model,
)


class _ProfileResult(BaseModel):
    answer: str


@pytest.mark.parametrize(
    "model,reasoning_effort",
    [
        ("groq:openai/gpt-oss-120b", "high"),
        ("groq:openai/gpt-oss-20b", None),
        ("groq:unknown-model", None),
        ("unknown:openai/gpt-oss-120b", None),
        ("openai:openai/gpt-oss-120b", None),
    ],
)
def test_documentation_profile_preserves_settings_without_an_action_deadline(
    model, reasoning_effort
):
    profile = resolve_assistant_model(model=model)

    expected = {
        "temperature": 0.3,
        "parallel_tool_calls": False,
        "max_tokens": 16384,
    }
    if reasoning_effort is not None:
        expected["extra_body"] = {"reasoning_effort": reasoning_effort}

    assert profile.get_settings(DOCUMENTATION) == expected
    assert profile.get_settings(SUBAGENT) == {**expected, "timeout": 20}


@pytest.mark.parametrize(
    "model", ["groq:openai/gpt-oss-120b", "groq:openai/gpt-oss-20b"]
)
def test_native_output_is_limited_to_documentation_for_registered_models(model):
    profile = resolve_assistant_model(model=model)

    output_type = profile.get_output_type(_ProfileResult, DOCUMENTATION)

    assert isinstance(output_type, NativeOutput)
    assert output_type.outputs is _ProfileResult
    assert output_type.strict is True
    for role in (ORCHESTRATOR, SUBAGENT, UTILITY, SAMPLE, TITLE, SUGGESTIONS):
        assert profile.get_output_type(_ProfileResult, role) is _ProfileResult


@pytest.mark.parametrize(
    "model",
    [
        "groq:unknown-model",
        "unknown:openai/gpt-oss-120b",
        "openai:openai/gpt-oss-120b",
        "openai:openai/gpt-oss-20b",
        "groq:gpt-oss-120b",
        "groq:custom/gpt-oss-120b",
    ],
)
def test_unregistered_models_keep_the_default_structured_output_protocol(model):
    profile = resolve_assistant_model(model=model)

    assert profile.get_output_type(_ProfileResult, DOCUMENTATION) is _ProfileResult


@pytest.mark.parametrize("model", ["groq:gpt-oss-120b", "groq:custom/gpt-oss-120b"])
def test_shortened_groq_names_keep_their_existing_reasoning_settings(model):
    profile = resolve_assistant_model(model=model)

    for role in (SUBAGENT, DOCUMENTATION):
        assert profile.get_settings(role)["extra_body"] == {"reasoning_effort": "high"}
    assert "extra_body" not in profile.get_settings(ORCHESTRATOR)


def test_profile_settings_cannot_mutate_later_requests_or_other_roles():
    profile = resolve_assistant_model(model="groq:openai/gpt-oss-120b")
    first_settings = profile.get_settings(DOCUMENTATION)

    first_settings["temperature"] = 1
    first_settings["timeout"] = 1
    first_settings["extra_body"]["reasoning_effort"] = "low"

    for candidate in (
        profile,
        resolve_assistant_model(model="groq:openai/gpt-oss-120b"),
    ):
        for role in (DOCUMENTATION, SUBAGENT):
            subsequent = candidate.get_settings(role)
            assert subsequent["temperature"] == 0.3
            assert subsequent["extra_body"] == {"reasoning_effort": "high"}
        assert "timeout" not in candidate.get_settings(DOCUMENTATION)
        assert candidate.get_settings(SUBAGENT)["timeout"] == 20


@pytest.mark.parametrize("temperature", [0, 0.8])
def test_temperature_override_only_applies_to_the_orchestrator(settings, temperature):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE = temperature
    profile = resolve_assistant_model(model="groq:openai/gpt-oss-120b")

    assert profile.get_settings(ORCHESTRATOR)["temperature"] == temperature
    assert profile.get_settings(DOCUMENTATION)["temperature"] == 0.3
    assert profile.get_settings(SUBAGENT)["temperature"] == 0.3


@pytest.mark.parametrize("provider", ["google-gla", "google-vertex"])
def test_google_aliases_sanitize_documentation_and_temperature_overrides(
    settings, provider
):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE = 0.8
    profile = resolve_assistant_model(model=f"{provider}:gemini-3.6-flash")

    for role in (ORCHESTRATOR, SUBAGENT, DOCUMENTATION):
        model_settings = profile.get_settings(role)
        assert "temperature" not in model_settings
        assert "top_p" not in model_settings
        assert "top_k" not in model_settings
    assert "timeout" not in profile.get_settings(DOCUMENTATION)


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
):
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
):
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


def _inherit_kuma_from_a_switched_off_instance_provider(data_fixture) -> Workspace:
    workspace = data_fixture.create_workspace()
    instance_provider = AIProviderHandler.create_provider(
        "openai",
        api_key="instance-key",
        models_data=[
            {"model_identifier": "gpt-5.4", "feature_types": [AI_PROVIDER_FEATURE_KUMA]}
        ],
    )
    AIProviderHandler.create_provider(
        "openai",
        workspace=workspace,
        api_key="workspace-key",
        models_data=[
            {
                "model_identifier": "gpt-5.4",
                "feature_types": [AI_PROVIDER_FEATURE_AI_FIELDS],
            }
        ],
    )
    AIProviderHandler.set_workspace_provider_enabled(
        workspace, instance_provider, False
    )
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        model=instance_provider.models.get(),
    )
    return workspace


@pytest.mark.django_db
def test_switched_off_workspace_builds_inherited_kuma_with_instance_credentials(
    data_fixture, settings
):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = ""
    workspace = _inherit_kuma_from_a_switched_off_instance_provider(data_fixture)

    model_profile = resolve_assistant_model(workspace=workspace)

    assert model_profile.source == "database"
    assert model_profile.model_string == "openai:gpt-5.4"
    assert model_profile.database_model.provider_config.workspace_id is None
    resolved_model = model_profile.create_model().wrapped
    assert resolved_model._provider.client.api_key == "instance-key"


@pytest.mark.django_db
def test_workspace_disabled_kuma_raises_even_when_inherited_model_is_valid(
    data_fixture, settings
):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = ""
    workspace = _inherit_kuma_from_a_switched_off_instance_provider(data_fixture)
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_DISABLED,
        workspace=workspace,
    )

    with pytest.raises(AssistantModelDisabledError):
        resolve_assistant_model(workspace=workspace)


def test_explicit_model_profile_does_not_load_persisted_provider_state(mocker):
    state_loader = mocker.patch(
        "baserow_enterprise.assistant.model_profiles.get_ai_provider_state"
    )

    model_profile = resolve_assistant_model(model="google-gla:gemini-test")

    assert model_profile.model_string == "google:gemini-test"
    assert model_profile.source == "explicit"
    state_loader.assert_not_called()
