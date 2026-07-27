from typing import Any

from django.conf import settings

from baserow.core.generative_ai.exceptions import GenerativeAITypeDoesNotExist
from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    generative_ai_model_type_registry,
)

from .constants import PROVIDER_ENVIRONMENT_SETTINGS
from .exceptions import AIProviderTypeNotSupported, InvalidAIProviderSettings


def get_supported_provider_type(provider_type: str) -> GenerativeAIModelType:
    if provider_type not in PROVIDER_ENVIRONMENT_SETTINGS:
        raise AIProviderTypeNotSupported(provider_type)
    try:
        return generative_ai_model_type_registry.get(provider_type)
    except GenerativeAITypeDoesNotExist as exc:
        raise AIProviderTypeNotSupported(provider_type) from exc


def get_provider_type_metadata() -> list[dict[str, Any]]:
    result = []
    for provider_type, environment_config in PROVIDER_ENVIRONMENT_SETTINGS.items():
        model_type = get_supported_provider_type(provider_type)
        serializer = model_type.get_settings_serializer()()
        required_extra_settings = set(
            environment_config.get("required_extra_settings", ())
        )
        extra_fields = []
        for name, field in serializer.fields.items():
            if name in {"api_key", "models"}:
                continue
            is_explicitly_required = name in required_extra_settings
            is_required = field.required or is_explicitly_required
            extra_fields.append(
                {
                    "name": name,
                    "required": is_required,
                    "allow_blank": (
                        getattr(field, "allow_blank", False)
                        and not is_explicitly_required
                    ),
                }
            )
        result.append(
            {
                "type": provider_type,
                "name": environment_config["name"],
                "uses_api_key": environment_config["api_key"] is not None,
                "extra_fields": extra_fields,
            }
        )
    return result


def validate_provider_settings(
    provider_type: str,
    api_key: str,
    extra_settings: dict[str, Any],
    model_identifiers: list[str],
    require_credentials: bool = False,
) -> dict[str, Any]:
    model_type = get_supported_provider_type(provider_type)
    serializer_class = model_type.get_settings_serializer()
    allowed_fields = set(serializer_class().fields)
    allowed_extra_fields = allowed_fields - {"api_key", "models"}
    unknown_fields = set(extra_settings) - allowed_extra_fields
    if unknown_fields:
        raise InvalidAIProviderSettings(
            {
                "extra_settings": [
                    f"Unsupported setting: {name}" for name in sorted(unknown_fields)
                ]
            }
        )

    values: dict[str, Any] = {
        "models": model_identifiers,
        **extra_settings,
    }
    if "api_key" in allowed_fields:
        if require_credentials and not api_key:
            raise InvalidAIProviderSettings(
                {"api_key": ["An API key is required for this provider type."]}
            )
        values["api_key"] = api_key

    if require_credentials:
        for name in PROVIDER_ENVIRONMENT_SETTINGS[provider_type].get(
            "required_extra_settings", ()
        ):
            if not extra_settings.get(name):
                raise InvalidAIProviderSettings(
                    {name: ["This setting is required for this provider type."]}
                )

    serializer = serializer_class(data=values)
    if not serializer.is_valid():
        raise InvalidAIProviderSettings(serializer.errors)

    validated = dict(serializer.validated_data)
    validated.pop("api_key", None)
    validated.pop("models", None)
    return {name: value for name, value in validated.items() if value not in (None, "")}


def get_environment_provider_values(provider_type: str) -> dict[str, Any]:
    config = PROVIDER_ENVIRONMENT_SETTINGS[provider_type]
    api_key_setting = config["api_key"]
    api_key = getattr(settings, api_key_setting, None) if api_key_setting else ""
    models = normalize_model_identifiers(getattr(settings, config["models"], []))
    extra_settings = {
        key: getattr(settings, setting_name, None)
        for key, setting_name in config["extra_settings"].items()
    }
    extra_settings = {
        key: value for key, value in extra_settings.items() if value not in (None, "")
    }
    return {
        "provider_type": provider_type,
        "api_key": api_key or "",
        "extra_settings": extra_settings,
        "models": models,
        "configured": bool(api_key or extra_settings or models),
    }


def get_legacy_workspace_provider_values(
    provider_type: str, values: Any
) -> dict[str, Any]:
    """Validate and normalize one legacy workspace provider configuration."""

    if not isinstance(values, dict):
        raise InvalidAIProviderSettings(
            {"settings": ["The provider settings must be an object."]}
        )

    config = PROVIDER_ENVIRONMENT_SETTINGS[provider_type]
    api_key = str(values.get("api_key") or "")
    models = normalize_model_identifiers(values.get("models"))
    extra_settings = {
        name: values[name]
        for name in config["extra_settings"]
        if values.get(name) not in (None, "")
    }
    validated_extra_settings = validate_provider_settings(
        provider_type,
        api_key,
        extra_settings,
        models,
        require_credentials=True,
    )
    return {
        "provider_type": provider_type,
        "api_key": api_key,
        "extra_settings": validated_extra_settings,
        "models": models,
    }


def normalize_model_identifiers(values: str | list[str] | None) -> list[str]:
    if isinstance(values, str):
        values = values.split(",")
    result = []
    seen = set()
    for raw_value in values or []:
        value = str(raw_value).strip()
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
