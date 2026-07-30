from unittest.mock import patch

from django.db import IntegrityError

import pytest

from baserow.core.ai_provider.handler import AIProviderHandler
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
