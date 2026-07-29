from unittest.mock import patch

from django.db import IntegrityError
from django.utils import timezone

import pytest

from baserow.core.ai_provider.exceptions import (
    AIProviderTypeAlreadyConfigured,
    InvalidAIProviderSettings,
)
from baserow.core.ai_provider.handler import (
    AIProviderHandler,
    WorkspaceAIProviderConfig,
)
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel


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
    }

    with patch.object(AIProviderHandler, "_test_model", return_value=result) as test:
        AIProviderHandler.test_models([model])

    assert test.call_args.args[2] == {
        "api_key": "workspace-key",
        "models": ["workspace-model"],
        "organization": "workspace-org",
        "base_url": None,
    }
