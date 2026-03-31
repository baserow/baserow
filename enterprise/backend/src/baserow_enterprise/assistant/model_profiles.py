"""
Centralized model configuration and per-model settings for all agents.

Contains:
- ``get_model_string()``: Resolves the active LLM model identifier.
- ``check_lm_ready_or_raise()``: Quick connectivity check.
- ``get_model_settings(model, role)``: Per-model, per-role settings.

Usage::

    from baserow_enterprise.assistant.model_profiles import (
        get_model_string, get_model_settings, ORCHESTRATOR,
    )

    model = get_model_string()
    settings = get_model_settings(model, ORCHESTRATOR)
"""

from functools import lru_cache

from django.conf import settings

from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings

from baserow_enterprise.assistant.exceptions import AssistantModelNotSupportedError
from baserow_enterprise.assistant.models import AssistantChat

# ---------------------------------------------------------------------------
# Agent roles
# ---------------------------------------------------------------------------

ORCHESTRATOR = "orchestrator"
SUBAGENT = "subagent"  # database, builder, automations
UTILITY = "utility"  # formula, fixer (precision-oriented)
SAMPLE = "sample"  # sample row generation (creative)
TITLE = "title"  # title generation

# ---------------------------------------------------------------------------
# Per-model profiles
# ---------------------------------------------------------------------------

# Fallback when the model isn't in _MODEL_PROFILES
_DEFAULT_PROFILE: dict[str, ModelSettings] = {
    ORCHESTRATOR: {
        "temperature": 0.3,
        "timeout": 30,
        "parallel_tool_calls": False,
        "max_tokens": 16384,
    },
    SUBAGENT: {
        "temperature": 0.3,
        "timeout": 20,
        "parallel_tool_calls": False,
        "max_tokens": 16384,
    },
    UTILITY: {
        "temperature": 0.1,
        "timeout": 20,
    },
    SAMPLE: {
        "temperature": 0.5,
        "timeout": 20,
    },
    TITLE: {
        "temperature": 0.7,
        "timeout": 10,
        "max_tokens": AssistantChat.TITLE_MAX_LENGTH,
    },
}

_MODEL_PROFILES: dict[str, dict[str, ModelSettings]] = {
    "gpt-oss-120b": {
        ORCHESTRATOR: {
            **_DEFAULT_PROFILE[ORCHESTRATOR],
            "groq_reasoning_format": "parsed",
        },
        SUBAGENT: {
            **_DEFAULT_PROFILE[SUBAGENT],
            "groq_reasoning_format": "parsed",
        },
        UTILITY: {
            # No groq_reasoning_format here: formula generation is a precise
            # structured-output task where reasoning tokens pollute the output.
            **_DEFAULT_PROFILE[UTILITY],
        },
        SAMPLE: {
            **_DEFAULT_PROFILE[SAMPLE],
            "groq_reasoning_format": "parsed",
        },
        TITLE: {
            **_DEFAULT_PROFILE[TITLE],
        },
    },
}


def get_model_settings(model: str, role: str) -> ModelSettings:
    """
    Return the ModelSettings for a given model string and agent role.

    The model string is the pydantic-ai format (e.g. ``"groq:openai/gpt-oss-120b"``).
    We match on the last path segment (e.g. ``"gpt-oss-120b"``) to find the profile.

    For the ``ORCHESTRATOR`` role the temperature defaults to the value of
    ``BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE`` (if set), allowing
    operators to override it without changing code.

    :param model: pydantic-ai model string (e.g. ``"groq:openai/gpt-oss-120b"``).
    :param role: One of ORCHESTRATOR, SUBAGENT, UTILITY, TITLE.
    :return: A ModelSettings dict suitable for ``model_settings=`` parameter.
    """

    # Extract model name after the provider prefix:
    #   "groq:openai/gpt-oss-120b" -> "gpt-oss-120b"
    #   "ollama:kimi-2.5:cloud"    -> "kimi-2.5:cloud"
    _, sep, after_provider = model.partition(":")
    model_name = after_provider.rsplit("/", 1)[-1] if sep else model

    profile = _MODEL_PROFILES.get(model_name, _DEFAULT_PROFILE)
    result = dict(profile.get(role, _DEFAULT_PROFILE.get(role, {})))

    # Allow the env-var-driven setting to override the orchestrator temperature.
    if role == ORCHESTRATOR:
        env_temp = getattr(
            settings, "BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE", None
        )
        if env_temp is not None:
            result["temperature"] = env_temp

    return result


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


def get_model_string(model: str | None = None) -> str:
    """
    Returns the model string for the pydantic-ai agent.

    :param model: The language model to use. If None, the default model from
        settings will be used.
    :return: A model string compatible with pydantic-ai.
    """

    value = model or settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL
    # pydantic-ai expects "provider:model" (e.g. "groq:openai/gpt-oss-120b").
    # Convert "provider/model" to "provider:model" when the first "/" comes
    # before the first ":" (or there is no ":").  This handles cases like
    # "ollama/kimi-2.5:cloud" where the colon is part of the model tag.
    slash_pos = value.find("/")
    colon_pos = value.find(":")
    if slash_pos != -1 and (colon_pos == -1 or slash_pos < colon_pos):
        value = value.replace("/", ":", 1)
    elif slash_pos == -1 and colon_pos == -1:
        # No provider prefix at all (e.g. "gpt-4o") — default to OpenAI
        # for backward compatibility with old UDSPY_LM_MODEL values.
        value = f"openai:{value}"
    return value


@lru_cache(maxsize=1)
def check_lm_ready_or_raise() -> None:
    from baserow_enterprise.assistant.retrying_model import _resolve_model

    model = get_model_string()
    test_agent = Agent(
        output_type=str, instructions="Respond with 'ok'.", name="test_agent"
    )
    try:
        test_agent.run_sync("Test", model=_resolve_model(model))
    except Exception as e:
        raise AssistantModelNotSupportedError(
            f"The model '{model}' is not supported or accessible: {e}"
        )
