AI_PROVIDER_TEST_STATUS_SUCCESS = "success"
AI_PROVIDER_TEST_STATUS_FAILURE = "failure"

AI_PROVIDER_FEATURE_AI_FIELDS = "ai_fields"
AI_PROVIDER_FEATURE_KUMA = "kuma"
AI_PROVIDER_FEATURE_AI_AGENT = "ai_agent"

AI_PROVIDER_FEATURE_MODE_INHERIT = "inherit"
AI_PROVIDER_FEATURE_MODE_LEGACY = "legacy"
AI_PROVIDER_FEATURE_MODE_MODEL = "model"
AI_PROVIDER_FEATURE_MODE_DISABLED = "disabled"
AI_PROVIDER_FEATURE_MODES = (
    AI_PROVIDER_FEATURE_MODE_INHERIT,
    AI_PROVIDER_FEATURE_MODE_LEGACY,
    AI_PROVIDER_FEATURE_MODE_MODEL,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
)

# Reasoning models spend tokens before emitting content, so a budget that only fits a
# short answer makes a working model look broken. Every probe uses the same one.
AI_PROVIDER_TEST_MAX_TOKENS = 256
AI_PROVIDER_TEST_TIMEOUT_SECONDS = 30

AI_PROVIDER_MODEL_CAPABILITY_TEXT = "text"
AI_PROVIDER_MODEL_CAPABILITY_TOOLS = "tools"
AI_PROVIDER_MODEL_CAPABILITIES = (
    AI_PROVIDER_MODEL_CAPABILITY_TEXT,
    AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
)

AI_PROVIDER_TYPES = {
    "openai": {
        "name": "OpenAI",
        "uses_api_key": True,
        "extra_settings": ("organization", "base_url"),
    },
    "anthropic": {
        "name": "Anthropic",
        "uses_api_key": True,
        "extra_settings": (),
    },
    "google": {
        "name": "Google Gemini",
        "uses_api_key": True,
        "extra_settings": (),
    },
    "groq": {
        "name": "Groq",
        "uses_api_key": True,
        "extra_settings": (),
    },
    "mistral": {
        "name": "Mistral",
        "uses_api_key": True,
        "extra_settings": (),
    },
    "ollama": {
        "name": "Ollama",
        "uses_api_key": False,
        "extra_settings": ("host",),
        "required_extra_settings": ("host",),
    },
    "openrouter": {
        "name": "OpenRouter",
        "uses_api_key": True,
        "extra_settings": ("organization",),
    },
}

# Legacy env-var mapping for the import command only; slated for removal, never extend.
PROVIDER_ENVIRONMENT_SETTINGS = {
    "openai": {
        "api_key": "BASEROW_OPENAI_API_KEY",
        "models": "BASEROW_OPENAI_MODELS",
        "extra_settings": {
            "organization": "BASEROW_OPENAI_ORGANIZATION",
            "base_url": "BASEROW_OPENAI_BASE_URL",
        },
    },
    "anthropic": {
        "api_key": "BASEROW_ANTHROPIC_API_KEY",
        "models": "BASEROW_ANTHROPIC_MODELS",
        "extra_settings": {},
    },
    "mistral": {
        "api_key": "BASEROW_MISTRAL_API_KEY",
        "models": "BASEROW_MISTRAL_MODELS",
        "extra_settings": {},
    },
    "ollama": {
        "api_key": None,
        "models": "BASEROW_OLLAMA_MODELS",
        "extra_settings": {"host": "BASEROW_OLLAMA_HOST"},
    },
    "openrouter": {
        "api_key": "BASEROW_OPENROUTER_API_KEY",
        "models": "BASEROW_OPENROUTER_MODELS",
        "extra_settings": {
            "organization": "BASEROW_OPENROUTER_ORGANIZATION",
        },
    },
}
