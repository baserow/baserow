"""Request defaults shared by AI features, without credentials or feature settings."""

from copy import deepcopy

from pydantic_ai.settings import ModelSettings

from .exceptions import GenerativeAITypeDoesNotExist
from .registries import generative_ai_model_type_registry

AGENT = "agent"
ORCHESTRATOR = "orchestrator"
SUBAGENT = "subagent"  # database, builder, automations
DOCUMENTATION = "documentation"  # source-backed answers without action tools
UTILITY = "utility"  # formula, fixer (precision-oriented)
SAMPLE = "sample"  # sample row generation (creative)
TITLE = "title"
SUGGESTIONS = "suggestions"  # onboarding prompt suggestions (creative)

# These are task budgets, not the models' maximum supported output lengths.
_DEFAULT_PROFILE: dict[str, ModelSettings] = {
    AGENT: {},
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
    DOCUMENTATION: {
        "temperature": 0.3,
        "parallel_tool_calls": False,
        "max_tokens": 16384,
        # Keep the provider timeout used by documentation synthesis.
    },
    SAMPLE: {
        "temperature": 0.5,
        "timeout": 20,
    },
    TITLE: {
        "temperature": 0.7,
        # Gemini rejects deadlines under 10s, so stay clear of the floor.
        "timeout": 15,
    },
    SUGGESTIONS: {
        "temperature": 0.6,
        "timeout": 30,
        "max_tokens": 4096,
    },
}


def get_role_defaults(role: str) -> ModelSettings:
    """Return independent task defaults, preserving SDK defaults for unknown roles."""

    return deepcopy(_DEFAULT_PROFILE.get(role, {}))


def get_model_settings(model: str, role: str) -> ModelSettings:
    """
    Return independent task defaults and provider/model overrides for one call.

    Callers apply feature-specific settings and explicit choices, then sanitize
    the combined settings for their provider. Unknown roles have no defaults.

    :param model: Pydantic AI identifier, such as ``groq:openai/gpt-oss-120b``.
    :param role: The task the model performs, such as ORCHESTRATOR or TITLE.
    :return: A fresh settings mapping, including fresh nested values.
    """

    provider, _, model_name = model.partition(":")
    try:
        model_type = generative_ai_model_type_registry.get(provider)
    except GenerativeAITypeDoesNotExist:
        return get_role_defaults(role)
    return model_type.get_model_settings(model_name, role)
