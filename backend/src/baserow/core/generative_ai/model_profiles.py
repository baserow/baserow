"""Request defaults shared by AI features, without credentials or feature settings."""

from copy import deepcopy

from pydantic_ai.settings import ModelSettings

ORCHESTRATOR = "orchestrator"
SUBAGENT = "subagent"  # database, builder, automations
DOCUMENTATION = "documentation"  # source-backed answers without action tools
UTILITY = "utility"  # formula, fixer (precision-oriented)
SAMPLE = "sample"  # sample row generation (creative)
TITLE = "title"
SUGGESTIONS = "suggestions"  # onboarding prompt suggestions (creative)

# These are task budgets, not the models' maximum supported output lengths.
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
        "max_tokens": 250,
    },
    SUGGESTIONS: {
        "temperature": 0.6,
        "timeout": 30,
        "max_tokens": 4096,
    },
}

# Settings historically match provider plus the last model-name segment.
_MODEL_SETTINGS_OVERRIDES: dict[tuple[str, str], dict[str, ModelSettings]] = {
    ("groq", "gpt-oss-120b"): {
        # Groq GPT-OSS accepts reasoning_effort, but rejects reasoning_format.
        SUBAGENT: {"extra_body": {"reasoning_effort": "high"}},
        DOCUMENTATION: {"extra_body": {"reasoning_effort": "high"}},
    },
}


def get_model_settings(model: str, role: str) -> ModelSettings:
    """
    Return independent task defaults and provider/model overrides for one call.

    Callers apply feature-specific settings and explicit choices, then sanitize
    the combined settings for their provider. Unknown roles have no defaults.

    :param model: Pydantic AI identifier, such as ``groq:openai/gpt-oss-120b``.
    :param role: The task the model performs, such as ORCHESTRATOR or TITLE.
    :return: A fresh settings mapping, including fresh nested values.
    """

    provider, sep, after_provider = model.partition(":")
    model_name = after_provider.rsplit("/", 1)[-1] if sep else model
    overrides = _MODEL_SETTINGS_OVERRIDES.get((provider, model_name), {})
    result = deepcopy(_DEFAULT_PROFILE.get(role, {}))
    result.update(deepcopy(overrides.get(role, {})))
    return result
