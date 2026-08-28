from unittest.mock import patch

from django.db import IntegrityError
from django.utils import timezone

import pytest
from pydantic_ai.models.test import TestModel

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_AI_FIELDS,
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
    AI_PROVIDER_FEATURE_MODE_INHERIT,
    AI_PROVIDER_FEATURE_MODE_LEGACY,
    AI_PROVIDER_FEATURE_MODE_MODEL,
    AI_PROVIDER_MODEL_CAPABILITY_TEXT,
    AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
    AI_PROVIDER_TEST_MAX_TOKENS,
)
from baserow.core.ai_provider.exceptions import (
    AIProviderDoesNotExist,
    AIProviderFeatureModelNotAvailable,
    AIProviderModelDoesNotExist,
    AIProviderModelInUse,
    AIProviderTypeAlreadyConfigured,
    InvalidAIProviderSettings,
)
from baserow.core.ai_provider.handler import (
    AIProviderHandler,
    WorkspaceAIProviderConfig,
)
from baserow.core.ai_provider.models import (
    AIProviderConfig,
    AIProviderFeatureSetting,
    AIProviderModel,
)
from baserow.core.ai_provider.registries import (
    ai_provider_model_feature_type_registry,
)
from baserow.core.generative_ai.generative_ai_model_types import (
    GoogleGenerativeAIModelType,
    GroqGenerativeAIModelType,
    MistralGenerativeAIModelType,
)


@pytest.mark.django_db
def test_create_provider_does_not_misreport_unexpected_integrity_error():
    unexpected_error = IntegrityError("unexpected integrity error")

    with patch.object(
        AIProviderConfig.objects,
        "create",
        side_effect=unexpected_error,
    ):
        with pytest.raises(IntegrityError, match="unexpected integrity error"):
            AIProviderHandler.create_provider("openai", api_key="secret")


@pytest.mark.django_db
def test_create_model_does_not_misreport_unexpected_integrity_error():
    provider = AIProviderConfig.objects.create(provider_type="openai", api_key="secret")
    unexpected_error = IntegrityError("unexpected integrity error")

    with patch.object(
        AIProviderModel.objects,
        "create",
        side_effect=unexpected_error,
    ):
        with pytest.raises(IntegrityError, match="unexpected integrity error"):
            AIProviderHandler.create_model(provider, model_identifier="gpt-5.4")


@pytest.mark.django_db
def test_omitted_model_feature_types_remain_ai_fields_only():
    provider = AIProviderHandler.create_provider(
        "openai",
        api_key="secret",
        models_data=[{"model_identifier": "gpt-5.4"}],
    )

    assert provider.models.get().feature_types == [AI_PROVIDER_FEATURE_AI_FIELDS]


@pytest.mark.django_db
def test_provider_credentials_are_trimmed_on_create_and_update():
    provider = AIProviderHandler.create_provider("openai", api_key="  secret  ")

    assert provider.api_key == "secret"

    provider = AIProviderHandler.update_provider(provider, api_key="  updated  ")

    assert provider.api_key == "updated"


@pytest.mark.django_db
def test_update_model_does_not_misreport_unexpected_integrity_error():
    provider = AIProviderConfig.objects.create(provider_type="openai", api_key="secret")
    model = AIProviderModel.objects.create(
        provider_config=provider, model_identifier="gpt-5.4"
    )
    unexpected_error = IntegrityError("unexpected integrity error")

    with patch.object(model, "save", side_effect=unexpected_error):
        with pytest.raises(IntegrityError, match="unexpected integrity error"):
            AIProviderHandler.update_model(model, model_identifier="gpt-5.4-mini")


def test_test_error_sanitization_redacts_overlapping_secrets_longest_first():
    message = AIProviderHandler._sanitize_test_error(
        Exception("failed with secret-token and secret"),
        ["secret", "secret-token", "", "secret-token"],
    )

    assert message == "failed with [redacted] and [redacted]"
    assert "token" not in message


def test_test_error_sanitization_ignores_empty_secrets_and_truncates():
    message = AIProviderHandler._sanitize_test_error(
        Exception("x" * 1001),
        [""],
    )

    assert message == "x" * 1000


def test_secret_values_ignores_non_string_extra_settings():
    values = AIProviderHandler._secret_values(
        "api-key",
        {
            "host": "secret-host",
            "timeout": 30,
            "enabled": True,
            "options": {"secret": "nested-secret"},
        },
    )

    assert values == ["api-key", "secret-host"]


@pytest.mark.django_db
def test_provider_type_is_unique_per_instance_or_workspace(data_fixture):
    workspace_a = data_fixture.create_workspace()
    workspace_b = data_fixture.create_workspace()

    instance_provider = AIProviderHandler.create_provider(
        "openai", api_key="instance-key"
    )
    workspace_a_provider = AIProviderHandler.create_provider(
        "openai", api_key="workspace-a-key", workspace=workspace_a
    )
    workspace_b_provider = AIProviderHandler.create_provider(
        "openai", api_key="workspace-b-key", workspace=workspace_b
    )

    assert instance_provider.workspace_id is None
    assert workspace_a_provider.workspace_id == workspace_a.id
    assert workspace_b_provider.workspace_id == workspace_b.id
    with pytest.raises(AIProviderTypeAlreadyConfigured):
        AIProviderHandler.create_provider(
            "openai", api_key="duplicate-key", workspace=workspace_a
        )


@pytest.mark.django_db
def test_workspace_provider_list_uses_an_explicit_scoped_representation(data_fixture):
    workspace = data_fixture.create_workspace()
    provider = AIProviderHandler.create_provider(
        "openai",
        api_key="instance-key",
        extra_settings={"base_url": "https://instance.example"},
        models_data=[{"model_identifier": "gpt-5.6"}],
    )

    scoped_provider = AIProviderHandler.list_providers(workspace)[0]

    assert isinstance(scoped_provider, WorkspaceAIProviderConfig)
    assert scoped_provider.id == provider.id
    assert scoped_provider.extra_settings == {}
    assert scoped_provider.is_active is True
    assert scoped_provider.workspace_enabled is True
    assert scoped_provider.read_only is True
    assert [model.model_identifier for model in scoped_provider.models] == ["gpt-5.6"]
    assert not hasattr(provider, "workspace_enabled")


@pytest.mark.django_db
def test_models_require_their_own_provider_credentials(data_fixture):
    workspace = data_fixture.create_workspace()
    provider = AIProviderConfig.objects.create(
        workspace=workspace,
        provider_type="openai",
        api_key="",
    )

    with pytest.raises(InvalidAIProviderSettings) as exc_info:
        AIProviderHandler.create_model(
            provider, model_identifier="expensive-workspace-model"
        )

    assert "api_key" in exc_info.value.errors

    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="existing-workspace-model",
    )
    with pytest.raises(InvalidAIProviderSettings) as exc_info:
        AIProviderHandler.update_model(
            model, model_identifier="expensive-workspace-model"
        )

    assert "api_key" in exc_info.value.errors


@pytest.mark.django_db
def test_changing_provider_connection_clears_stale_model_test_results():
    provider = AIProviderConfig.objects.create(
        provider_type="openai",
        api_key="old-key",
        extra_settings={"organization": "old-org"},
    )
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="test-model",
        last_test_at=timezone.now(),
        last_test_status=AIProviderModel.TestStatus.SUCCESS,
        last_test_error="",
        last_test_capabilities={
            AI_PROVIDER_MODEL_CAPABILITY_TEXT: {
                "status": AIProviderModel.TestStatus.SUCCESS,
                "error": "",
            }
        },
    )

    AIProviderHandler.update_provider(
        provider,
        api_key="new-key",
        extra_settings={"organization": "new-org"},
    )

    model.refresh_from_db()
    assert model.last_test_at is None
    assert model.last_test_status is None
    assert model.last_test_error == ""
    assert model.last_test_capabilities == {}


@pytest.mark.django_db
def test_changing_model_identifier_clears_stale_test_result():
    provider = AIProviderConfig.objects.create(provider_type="openai", api_key="key")
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="old-model",
        last_test_at=timezone.now(),
        last_test_status=AIProviderModel.TestStatus.FAILURE,
        last_test_error="Old failure",
        last_test_capabilities={
            AI_PROVIDER_MODEL_CAPABILITY_TEXT: {
                "status": AIProviderModel.TestStatus.FAILURE,
                "error": "Old failure",
            }
        },
    )

    model = AIProviderHandler.update_model(model, model_identifier="new-model")

    assert model.last_test_at is None
    assert model.last_test_status is None
    assert model.last_test_error == ""
    assert model.last_test_capabilities == {}


@pytest.mark.django_db
def test_changing_model_features_clears_stale_test_result():
    provider = AIProviderConfig.objects.create(provider_type="openai", api_key="key")
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="model",
        feature_types=[AI_PROVIDER_FEATURE_AI_FIELDS],
        last_test_at=timezone.now(),
        last_test_status=AIProviderModel.TestStatus.SUCCESS,
        last_test_capabilities={
            AI_PROVIDER_MODEL_CAPABILITY_TEXT: {
                "status": AIProviderModel.TestStatus.SUCCESS,
                "error": "",
            }
        },
    )

    model = AIProviderHandler.update_model(
        model,
        feature_types=[AI_PROVIDER_FEATURE_AI_FIELDS, AI_PROVIDER_FEATURE_KUMA],
    )

    assert model.last_test_at is None
    assert model.last_test_status is None
    assert model.last_test_error == ""
    assert model.last_test_capabilities == {}


def test_text_and_tools_probe_requires_a_real_tool_call():
    model_type = MistralGenerativeAIModelType()

    with patch.object(
        model_type,
        "get_ai_model",
        return_value=TestModel(call_tools=[], custom_output_text="OK"),
    ):
        results = AIProviderHandler._test_text_and_tools(
            model_type,
            "model",
            settings_override={},
            secret_values=[],
        )

    assert results == {
        AI_PROVIDER_MODEL_CAPABILITY_TEXT: {
            "status": AIProviderModel.TestStatus.SUCCESS,
            "error": "",
        },
        AI_PROVIDER_MODEL_CAPABILITY_TOOLS: {
            "status": AIProviderModel.TestStatus.FAILURE,
            "error": "The model did not call the compatibility test tool.",
        },
    }


def test_text_and_tools_probe_passes_when_the_model_calls_the_tool():
    model_type = MistralGenerativeAIModelType()

    with patch.object(
        model_type,
        "get_ai_model",
        return_value=TestModel(call_tools="all"),
    ):
        results = AIProviderHandler._test_text_and_tools(
            model_type,
            "model",
            settings_override={},
            secret_values=[],
        )

    assert results == {
        AI_PROVIDER_MODEL_CAPABILITY_TEXT: {
            "status": AIProviderModel.TestStatus.SUCCESS,
            "error": "",
        },
        AI_PROVIDER_MODEL_CAPABILITY_TOOLS: {
            "status": AIProviderModel.TestStatus.SUCCESS,
            "error": "",
        },
    }


def test_both_probes_share_one_token_budget():
    model_type = MistralGenerativeAIModelType()
    text_budget = {}

    def capture_prompt(*args, model_settings_override=None, **kwargs):
        text_budget.update(model_settings_override or {})
        return "OK"

    with patch.object(model_type, "prompt", side_effect=capture_prompt):
        AIProviderHandler._test_text(
            model_type, "model", settings_override={}, secret_values=[]
        )

    tool_budget = {}

    def capture_tool_probe(model, max_tokens=None, **kwargs):
        tool_budget["max_tokens"] = max_tokens

    with (
        patch.object(model_type, "get_ai_model", return_value=TestModel()),
        patch(
            "baserow.core.ai_provider.handler.test_model_text_and_tool_calling",
            side_effect=capture_tool_probe,
        ),
    ):
        AIProviderHandler._test_text_and_tools(
            model_type, "model", settings_override={}, secret_values=[]
        )

    # A budget that only fits a short answer fails reasoning models before they emit
    # any content, so an AI-fields-only model must not be probed more tightly than a
    # Kuma one.
    assert text_budget["max_tokens"] == AI_PROVIDER_TEST_MAX_TOKENS
    assert tool_budget["max_tokens"] == AI_PROVIDER_TEST_MAX_TOKENS


def test_model_test_derives_each_feature_result_from_shared_capabilities():
    capability_results = {
        AI_PROVIDER_MODEL_CAPABILITY_TEXT: {
            "status": AIProviderModel.TestStatus.SUCCESS,
            "error": "",
        },
        AI_PROVIDER_MODEL_CAPABILITY_TOOLS: {
            "status": AIProviderModel.TestStatus.FAILURE,
            "error": "Tool calling is unavailable.",
        },
    }

    with patch.object(
        AIProviderHandler,
        "_test_text_and_tools",
        return_value=capability_results,
    ) as test_text_and_tools:
        result = AIProviderHandler._test_model(
            "mistral",
            "model",
            settings_override={"api_key": "secret", "models": ["model"]},
            secret_values=["secret"],
            model_id=1,
            feature_types=[AI_PROVIDER_FEATURE_AI_FIELDS, AI_PROVIDER_FEATURE_KUMA],
        )

    test_text_and_tools.assert_called_once()
    assert result["status"] == AIProviderModel.TestStatus.FAILURE
    assert result["error"] == "Tool calling is unavailable."
    assert result["feature_results"] == [
        {
            "feature_type": AI_PROVIDER_FEATURE_AI_FIELDS,
            "status": AIProviderModel.TestStatus.SUCCESS,
            "error": "",
        },
        {
            "feature_type": AI_PROVIDER_FEATURE_KUMA,
            "status": AIProviderModel.TestStatus.FAILURE,
            "error": "Tool calling is unavailable.",
        },
    ]


def test_model_test_treats_an_unregistered_persisted_feature_as_text_only(
    monkeypatch,
):
    monkeypatch.setattr(ai_provider_model_feature_type_registry, "registry", {})
    capability_result = {
        "status": AIProviderModel.TestStatus.SUCCESS,
        "error": "",
    }

    with patch.object(
        AIProviderHandler,
        "_test_text",
        return_value=capability_result,
    ) as test_text:
        result = AIProviderHandler._test_model(
            "mistral",
            "model",
            settings_override={"api_key": "secret", "models": ["model"]},
            secret_values=["secret"],
            model_id=1,
            feature_types=[AI_PROVIDER_FEATURE_AI_FIELDS],
        )

    test_text.assert_called_once()
    assert result["status"] == AIProviderModel.TestStatus.SUCCESS
    assert result["feature_results"] == [
        {
            "feature_type": AI_PROVIDER_FEATURE_AI_FIELDS,
            "status": AIProviderModel.TestStatus.SUCCESS,
            "error": "",
        }
    ]


@pytest.mark.parametrize(
    ("provider_type", "model_identifier", "model_type_class"),
    [
        ("google", "gemini-2.5-flash", GoogleGenerativeAIModelType),
        ("groq", "openai/gpt-oss-120b", GroqGenerativeAIModelType),
    ],
)
def test_google_and_groq_models_run_the_kuma_tool_compatibility_probe(
    provider_type, model_identifier, model_type_class
):
    settings_override = {
        "api_key": f"{provider_type}-key",
        "models": [model_identifier],
    }
    with patch.object(
        model_type_class,
        "get_ai_model",
        return_value=TestModel(call_tools="all"),
    ) as get_ai_model:
        result = AIProviderHandler._test_model(
            provider_type,
            model_identifier,
            settings_override=settings_override,
            secret_values=[settings_override["api_key"]],
            model_id=1,
            feature_types=[AI_PROVIDER_FEATURE_KUMA],
        )

    get_ai_model.assert_called_once_with(
        model_identifier,
        settings_override=settings_override,
    )
    assert result["status"] == AIProviderModel.TestStatus.SUCCESS
    assert result["feature_results"] == [
        {
            "feature_type": AI_PROVIDER_FEATURE_KUMA,
            "status": AIProviderModel.TestStatus.SUCCESS,
            "error": "",
        }
    ]


@pytest.mark.django_db
def test_model_test_uses_a_complete_provider_settings_override(data_fixture):
    workspace = data_fixture.create_workspace()
    provider = AIProviderConfig.objects.create(
        workspace=workspace,
        provider_type="openai",
        api_key="workspace-key",
        extra_settings={"organization": "workspace-org"},
    )
    model = AIProviderModel.objects.create(
        provider_config=provider, model_identifier="workspace-model"
    )
    result = {
        "model_id": model.id,
        "status": "success",
        "error": "",
        "tested_at": timezone.now(),
        "capability_results": {
            AI_PROVIDER_MODEL_CAPABILITY_TEXT: {"status": "success", "error": ""}
        },
        "feature_results": [
            {
                "feature_type": AI_PROVIDER_FEATURE_AI_FIELDS,
                "status": "success",
                "error": "",
            }
        ],
    }

    with patch.object(AIProviderHandler, "_test_model", return_value=result) as test:
        AIProviderHandler.test_models([model])

    assert test.call_args.args[2] == {
        "api_key": "workspace-key",
        "models": ["workspace-model"],
        "organization": "workspace-org",
        "base_url": None,
    }


@pytest.mark.django_db
def test_kuma_model_selection_inherits_overrides_and_disables(data_fixture):
    workspace = data_fixture.create_workspace()
    instance_provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="instance-key"
    )
    instance_model = AIProviderModel.objects.create(
        provider_config=instance_provider,
        model_identifier="instance-model",
        feature_types=[AI_PROVIDER_FEATURE_KUMA],
    )
    workspace_provider = AIProviderConfig.objects.create(
        workspace=workspace,
        provider_type="anthropic",
        api_key="workspace-key",
    )
    workspace_model = AIProviderModel.objects.create(
        provider_config=workspace_provider,
        model_identifier="workspace-model",
        feature_types=[AI_PROVIDER_FEATURE_KUMA],
    )

    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        model=instance_model,
    )
    inherited = AIProviderHandler.list_feature_settings(workspace)[0]
    assert inherited["mode"] == AI_PROVIDER_FEATURE_MODE_INHERIT
    assert inherited["state"] == "inherited"
    assert inherited["model"] == instance_model

    overridden = AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        workspace=workspace,
        model=workspace_model,
    )
    assert overridden["state"] == "overridden"
    assert overridden["model"] == workspace_model

    disabled = AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_DISABLED,
        workspace=workspace,
    )
    assert disabled["state"] == "disabled"
    assert disabled["model"] is None

    inherited_again = AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_INHERIT,
        workspace=workspace,
    )
    assert inherited_again["state"] == "inherited"
    assert inherited_again["model"] == instance_model

    legacy_again = AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_LEGACY,
    )
    assert legacy_again["mode"] == AI_PROVIDER_FEATURE_MODE_LEGACY
    assert legacy_again["state"] == "unconfigured"
    assert not AIProviderFeatureSetting.objects.filter(workspace__isnull=True).exists()


@pytest.mark.django_db
def test_inherited_state_reports_why_an_instance_selection_is_unusable(data_fixture):
    workspace = data_fixture.create_workspace()
    instance_provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="instance-key"
    )
    instance_model = AIProviderModel.objects.create(
        provider_config=instance_provider,
        model_identifier="instance-model",
        feature_types=[AI_PROVIDER_FEATURE_KUMA],
    )

    unconfigured = AIProviderHandler.list_feature_settings(workspace)[0]
    assert unconfigured["inherited_state"] == "unconfigured"

    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        model=instance_model,
    )
    configured = AIProviderHandler.list_feature_settings(workspace)[0]
    assert configured["inherited_state"] == "configured"
    assert configured["inherited_model"] == instance_model

    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_DISABLED,
        workspace=workspace,
    )
    AIProviderHandler.set_workspace_provider_enabled(
        workspace, instance_provider, False
    )
    invalid = AIProviderHandler.list_feature_settings(workspace)[0]
    assert invalid["inherited_state"] == "invalid"
    assert invalid["inherited_model"] is None
    # The instance itself is still configured; only this workspace cannot resolve it.
    assert AIProviderHandler.list_feature_settings()[0]["state"] == "configured"

    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_DISABLED,
    )
    assert (
        AIProviderHandler.list_feature_settings(workspace)[0]["inherited_state"]
        == "disabled"
    )
    assert AIProviderHandler.list_feature_settings()[0]["inherited_state"] is None


@pytest.mark.django_db
def test_selected_feature_model_cannot_be_made_unusable():
    provider = AIProviderConfig.objects.create(provider_type="openai", api_key="secret")
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="kuma-model",
        feature_types=[AI_PROVIDER_FEATURE_KUMA],
    )
    unavailable_model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="ai-field-only-model",
        feature_types=["ai_fields"],
    )

    with pytest.raises(AIProviderFeatureModelNotAvailable):
        AIProviderHandler.update_feature_setting(
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_MODEL,
            model=unavailable_model,
        )

    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        model=model,
    )

    with pytest.raises(AIProviderModelInUse):
        AIProviderHandler.update_model(model, is_enabled=False)
    with pytest.raises(AIProviderModelInUse):
        AIProviderHandler.update_model(model, feature_types=[])
    with pytest.raises(AIProviderModelInUse):
        AIProviderHandler.delete_model(model)
    with pytest.raises(AIProviderModelInUse):
        AIProviderHandler.delete_provider(provider)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mutation",
    [
        "disable_model",
        "remove_model_feature",
        "delete_model",
        "disable_provider",
        "delete_provider",
    ],
)
def test_orphaned_optional_feature_selection_does_not_block_mutation(mutation):
    removed_feature_type = "removed_optional_feature"
    provider = AIProviderConfig.objects.create(provider_type="openai", api_key="secret")
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="optional-feature-model",
        feature_types=[removed_feature_type],
    )
    setting = AIProviderFeatureSetting.objects.create(
        feature_type=removed_feature_type,
        model=model,
        is_enabled=True,
    )

    if mutation == "disable_model":
        AIProviderHandler.update_model(model, is_enabled=False)
    elif mutation == "remove_model_feature":
        AIProviderHandler.update_model(model, feature_types=[])
    elif mutation == "delete_model":
        AIProviderHandler.delete_model(model)
    elif mutation == "disable_provider":
        AIProviderHandler.update_provider(provider, is_active=False)
    else:
        AIProviderHandler.delete_provider(provider)

    setting_exists = AIProviderFeatureSetting.objects.filter(id=setting.id).exists()
    if mutation in {"delete_model", "delete_provider"}:
        assert not setting_exists
    else:
        assert setting_exists


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("deleted_object", "expected_exception"),
    [
        ("model", AIProviderModelDoesNotExist),
        ("provider", AIProviderDoesNotExist),
    ],
)
def test_feature_selection_with_stale_model_raises_domain_error(
    deleted_object, expected_exception
):
    provider = AIProviderConfig.objects.create(provider_type="openai", api_key="secret")
    model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="kuma-model",
        feature_types=[AI_PROVIDER_FEATURE_KUMA],
    )
    model.provider_config = provider
    if deleted_object == "model":
        AIProviderModel.objects.filter(id=model.id).delete()
    else:
        AIProviderConfig.objects.filter(id=provider.id).delete()

    with pytest.raises(expected_exception):
        AIProviderHandler.update_feature_setting(
            AI_PROVIDER_FEATURE_KUMA,
            AI_PROVIDER_FEATURE_MODE_MODEL,
            model=model,
        )
