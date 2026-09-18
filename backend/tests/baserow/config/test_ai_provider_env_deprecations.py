import os
from unittest.mock import patch

import pytest
from loguru import logger

from baserow.config.helpers import log_ai_provider_env_deprecations
from baserow.core.ai_provider.constants import PROVIDER_ENVIRONMENT_SETTINGS

PROVIDER_VARIABLES = tuple(
    name
    for provider_settings in PROVIDER_ENVIRONMENT_SETTINGS.values()
    for name in (
        provider_settings["api_key"],
        provider_settings["models"],
        *provider_settings["extra_settings"].values(),
    )
    if name
)
KUMA_VARIABLES = (
    "BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL",
    "UDSPY_LM_MODEL",
    "UDSPY_LM_API_KEY",
    "UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL",
)


@pytest.fixture
def deprecation_messages():
    messages = []
    sink_id = logger.add(
        lambda message: messages.append(str(message)), format="{message}"
    )
    try:
        with patch.dict(os.environ, {}, clear=True):
            yield messages
    finally:
        logger.remove(sink_id)


@pytest.mark.parametrize("value", [None, "", " \t"])
def test_unconfigured_ai_provider_environment_does_not_warn(
    monkeypatch, deprecation_messages, value
):
    if value is not None:
        for name in (*PROVIDER_VARIABLES, *KUMA_VARIABLES):
            monkeypatch.setenv(name, value)

    log_ai_provider_env_deprecations()

    assert deprecation_messages == []


@pytest.mark.parametrize("name", PROVIDER_VARIABLES)
def test_provider_environment_warns_without_enterprise(
    monkeypatch, deprecation_messages, name
):
    monkeypatch.setenv(name, "private-value")

    with patch("baserow.config.helpers.apps.is_installed", return_value=False):
        log_ai_provider_env_deprecations()

    assert len(deprecation_messages) == 1
    message = deprecation_messages[0]
    assert name in message
    assert "private-value" not in message
    assert "migrate_ai_provider_settings --scope instance" in message


@pytest.mark.parametrize("name", KUMA_VARIABLES)
def test_kuma_environment_warns_when_enterprise_is_installed(
    monkeypatch, deprecation_messages, name
):
    monkeypatch.setenv(name, "private-value")

    with patch("baserow.config.helpers.apps.is_installed", return_value=True):
        log_ai_provider_env_deprecations()

    assert len(deprecation_messages) == 1
    message = deprecation_messages[0]
    assert name in message
    assert "private-value" not in message
    assert "select it for Kuma under AI features" in message


def test_kuma_environment_does_not_warn_without_enterprise(
    monkeypatch, deprecation_messages
):
    for name in KUMA_VARIABLES:
        monkeypatch.setenv(name, "private-value")

    with patch("baserow.config.helpers.apps.is_installed", return_value=False):
        log_ai_provider_env_deprecations()

    assert deprecation_messages == []


def test_ai_provider_environment_logs_only_names_once_per_group(
    monkeypatch, deprecation_messages
):
    values = {
        name: f"private-value-{index}"
        for index, name in enumerate((*PROVIDER_VARIABLES, *KUMA_VARIABLES))
    }
    values.update(
        BASEROW_OPENAI_API_KEY="private-api-key",
        BASEROW_OPENAI_BASE_URL="https://private.invalid/openai",
        BASEROW_OPENAI_MODELS="private-model-one,private-model-two",
        BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL="openai:private-kuma-model",
        UDSPY_LM_API_KEY="private-kuma-api-key",
        UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL="https://private.invalid/kuma",
    )
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    with patch("baserow.config.helpers.apps.is_installed", return_value=True):
        log_ai_provider_env_deprecations()

    assert len(deprecation_messages) == 2
    for name in PROVIDER_VARIABLES:
        assert name in deprecation_messages[0]
    for name in KUMA_VARIABLES:
        assert name in deprecation_messages[1]
    output = "\n".join(deprecation_messages)
    for value in values.values():
        assert value not in output
    assert "does not migrate Kuma selectors or SDK credentials" in output
    assert "Keep the environment fallback" in output
    assert all(os.environ[name] == value for name, value in values.items())


def test_supported_ai_environment_does_not_warn(monkeypatch, deprecation_messages):
    for name in (
        "BASEROW_OPENAI_UPLOADED_FILE_SIZE_LIMIT_MB",
        "BASEROW_AI_FIELD_MAX_CONCURRENT_GENERATIONS",
        "BASEROW_AI_FIELD_AUTO_UPDATE_DEBOUNCE_TIME",
        "BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "GOOGLE_API_KEY",
        "OLLAMA_BASE_URL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "AWS_REGION_NAME",
        "AWS_BEARER_TOKEN_BEDROCK",
    ):
        monkeypatch.setenv(name, "configured-value")

    log_ai_provider_env_deprecations()

    assert deprecation_messages == []
