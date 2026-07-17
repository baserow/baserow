AI_PROVIDER_TEST_STATUS_SUCCESS = "success"
AI_PROVIDER_TEST_STATUS_FAILURE = "failure"
AI_PROVIDER_CONFIGS_LOCAL_CACHE_KEY = "ai_provider_configs"

PROVIDER_ENVIRONMENT_SETTINGS = {
    "openai": {
        "name": "OpenAI",
        "api_key": "BASEROW_OPENAI_API_KEY",
        "models": "BASEROW_OPENAI_MODELS",
        "extra_settings": {
            "organization": "BASEROW_OPENAI_ORGANIZATION",
            "base_url": "BASEROW_OPENAI_BASE_URL",
        },
    },
    "anthropic": {
        "name": "Anthropic",
        "api_key": "BASEROW_ANTHROPIC_API_KEY",
        "models": "BASEROW_ANTHROPIC_MODELS",
        "extra_settings": {},
    },
    "mistral": {
        "name": "Mistral",
        "api_key": "BASEROW_MISTRAL_API_KEY",
        "models": "BASEROW_MISTRAL_MODELS",
        "extra_settings": {},
    },
    "ollama": {
        "name": "Ollama",
        "api_key": None,
        "models": "BASEROW_OLLAMA_MODELS",
        "extra_settings": {"host": "BASEROW_OLLAMA_HOST"},
        "required_extra_settings": ("host",),
    },
    "openrouter": {
        "name": "OpenRouter",
        "api_key": "BASEROW_OPENROUTER_API_KEY",
        "models": "BASEROW_OPENROUTER_MODELS",
        "extra_settings": {
            "organization": "BASEROW_OPENROUTER_ORGANIZATION",
        },
    },
}
