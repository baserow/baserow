from typing import Any

from django.db import IntegrityError
from django.utils import timezone

from baserow.core.cache import local_cache
from baserow.core.generative_ai.exceptions import get_user_friendly_error_message
from baserow.core.psycopg import is_unique_violation_error

from .constants import (
    AI_PROVIDER_CONFIGS_LOCAL_CACHE_KEY,
    AI_PROVIDER_TEST_STATUS_FAILURE,
    AI_PROVIDER_TEST_STATUS_SUCCESS,
)
from .exceptions import (
    AIProviderDoesNotExist,
    AIProviderModelAlreadyConfigured,
    AIProviderModelDoesNotExist,
    AIProviderTypeAlreadyConfigured,
)
from .models import AIProviderConfig, AIProviderModel
from .provider_types import (
    get_supported_provider_type,
    validate_provider_settings,
)


class AIProviderHandler:
    @staticmethod
    def _invalidate_resolution_cache() -> None:
        local_cache.delete(AI_PROVIDER_CONFIGS_LOCAL_CACHE_KEY)

    @staticmethod
    def list_providers():
        return AIProviderConfig.objects.prefetch_related("models").order_by("id")

    @staticmethod
    def get_provider(provider_id: int) -> AIProviderConfig:
        try:
            return AIProviderConfig.objects.prefetch_related("models").get(
                id=provider_id
            )
        except AIProviderConfig.DoesNotExist as exc:
            raise AIProviderDoesNotExist(provider_id) from exc

    @staticmethod
    def get_model(model_id: int) -> AIProviderModel:
        try:
            return AIProviderModel.objects.select_related("provider_config").get(
                id=model_id
            )
        except AIProviderModel.DoesNotExist as exc:
            raise AIProviderModelDoesNotExist(model_id) from exc

    @staticmethod
    def get_models(model_ids: list[int]) -> list[AIProviderModel]:
        models_by_id = {
            model.id: model
            for model in AIProviderModel.objects.filter(id__in=model_ids)
            .select_related("provider_config")
            .prefetch_related("provider_config__models")
        }
        for model_id in model_ids:
            if model_id not in models_by_id:
                raise AIProviderModelDoesNotExist(model_id)
        return [models_by_id[model_id] for model_id in model_ids]

    @staticmethod
    def _model_values(models_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        identifiers = set()
        for model in models_data:
            identifier = model["model_identifier"].strip()
            if identifier in identifiers:
                raise AIProviderModelAlreadyConfigured(identifier)
            identifiers.add(identifier)
            result.append(
                {
                    "model_identifier": identifier,
                    "is_enabled": model.get("is_enabled", True),
                }
            )
        return result

    @classmethod
    def create_provider(
        cls,
        provider_type: str,
        api_key: str = "",
        extra_settings: dict[str, Any] | None = None,
        models_data: list[dict[str, Any]] | None = None,
    ) -> AIProviderConfig:
        get_supported_provider_type(provider_type)
        if AIProviderConfig.objects.filter(provider_type=provider_type).exists():
            raise AIProviderTypeAlreadyConfigured(provider_type)

        extra_settings = extra_settings or {}
        models_data = cls._model_values(models_data or [])
        validated_extra_settings = validate_provider_settings(
            provider_type,
            api_key,
            extra_settings,
            [model["model_identifier"] for model in models_data],
            require_credentials=True,
        )
        try:
            provider = AIProviderConfig.objects.create(
                provider_type=provider_type,
                api_key=api_key,
                extra_settings=validated_extra_settings,
            )
        except IntegrityError as exc:
            if not is_unique_violation_error(exc):
                raise
            raise AIProviderTypeAlreadyConfigured(provider_type) from exc
        AIProviderModel.objects.bulk_create(
            [
                AIProviderModel(provider_config=provider, **model)
                for model in models_data
            ]
        )
        cls._invalidate_resolution_cache()
        return cls.get_provider(provider.id)

    @classmethod
    def update_provider(cls, provider: AIProviderConfig, **values) -> AIProviderConfig:
        api_key = values.get("api_key", provider.api_key)
        extra_settings = values.get("extra_settings", provider.extra_settings)
        model_identifiers = list(
            provider.models.order_by("id").values_list("model_identifier", flat=True)
        )
        validated_extra_settings = validate_provider_settings(
            provider.provider_type,
            api_key,
            extra_settings,
            model_identifiers,
            require_credentials=("api_key" in values or "extra_settings" in values),
        )
        allowed = {"api_key", "is_active"}
        update_fields = []
        for key, value in values.items():
            if key in allowed:
                setattr(provider, key, value)
                update_fields.append(key)
        if "extra_settings" in values:
            provider.extra_settings = validated_extra_settings
            update_fields.append("extra_settings")
        if update_fields:
            update_fields.append("updated_on")
            provider.save(update_fields=update_fields)
            cls._invalidate_resolution_cache()
        return cls.get_provider(provider.id)

    @staticmethod
    def delete_provider(provider: AIProviderConfig) -> None:
        provider.delete()
        AIProviderHandler._invalidate_resolution_cache()

    @classmethod
    def create_model(cls, provider: AIProviderConfig, **values) -> AIProviderModel:
        model_values = cls._model_values([values])[0]
        model_identifiers = list(
            provider.models.values_list("model_identifier", flat=True)
        ) + [model_values["model_identifier"]]
        validate_provider_settings(
            provider.provider_type,
            provider.api_key,
            provider.extra_settings,
            model_identifiers,
        )
        try:
            model = AIProviderModel.objects.create(
                provider_config=provider, **model_values
            )
        except IntegrityError as exc:
            if not is_unique_violation_error(exc):
                raise
            raise AIProviderModelAlreadyConfigured(
                model_values["model_identifier"]
            ) from exc
        cls._invalidate_resolution_cache()
        return model

    @classmethod
    def update_model(cls, model: AIProviderModel, **values) -> AIProviderModel:
        if "model_identifier" in values:
            values["model_identifier"] = values["model_identifier"].strip()
        model_identifiers = list(
            model.provider_config.models.exclude(id=model.id).values_list(
                "model_identifier", flat=True
            )
        )
        model_identifiers.append(values.get("model_identifier", model.model_identifier))
        validate_provider_settings(
            model.provider_config.provider_type,
            model.provider_config.api_key,
            model.provider_config.extra_settings,
            model_identifiers,
        )
        allowed = {"model_identifier", "is_enabled"}
        update_fields = []
        for key, value in values.items():
            if key in allowed:
                setattr(model, key, value)
                update_fields.append(key)
        if update_fields:
            try:
                model.save(update_fields=update_fields)
            except IntegrityError as exc:
                if not is_unique_violation_error(exc):
                    raise
                raise AIProviderModelAlreadyConfigured(model.model_identifier) from exc
            cls._invalidate_resolution_cache()
        return cls.get_model(model.id)

    @staticmethod
    def delete_model(model: AIProviderModel) -> None:
        model.delete()
        AIProviderHandler._invalidate_resolution_cache()

    @staticmethod
    def discover_models(provider_type: str) -> list[str] | None:
        model_type = get_supported_provider_type(provider_type)
        return model_type.get_known_models()

    @classmethod
    def _test_model(
        cls,
        provider_type: str,
        model_identifier: str,
        settings_override: dict[str, Any],
        secret_values: list[str],
        model_id: int | None = None,
    ) -> dict[str, Any]:
        model_type = get_supported_provider_type(provider_type)
        try:
            model_type.prompt(
                model_identifier,
                "OK",
                settings_override=settings_override,
                model_settings_override={"max_tokens": 16},
            )
        except Exception as exc:
            status = AI_PROVIDER_TEST_STATUS_FAILURE
            error = cls._sanitize_test_error(exc, secret_values)
        else:
            status = AI_PROVIDER_TEST_STATUS_SUCCESS
            error = ""

        return {
            "model_id": model_id,
            "model_identifier": model_identifier,
            "status": status,
            "error": error,
            "tested_at": timezone.now(),
        }

    @classmethod
    def test_models(cls, models: list[AIProviderModel]) -> list[dict[str, Any]]:
        results = []
        for model in models:
            provider = model.provider_config
            settings_override = dict(provider.extra_settings)
            settings_override["api_key"] = provider.api_key
            settings_override["models"] = [
                configured_model.model_identifier
                for configured_model in provider.models.all()
            ]
            result = cls._test_model(
                provider.provider_type,
                model.model_identifier,
                settings_override,
                cls._secret_values(provider.api_key, provider.extra_settings),
                model.id,
            )
            model.last_test_at = result["tested_at"]
            model.last_test_status = result["status"]
            model.last_test_error = result["error"]
            model.save(
                update_fields=("last_test_at", "last_test_status", "last_test_error")
            )
            results.append(result)
        return results

    @classmethod
    def test_unsaved_models(
        cls,
        provider_type: str,
        model_identifiers: list[str],
        api_key: str = "",
        extra_settings: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        extra_settings = extra_settings or {}
        model_identifiers = [identifier.strip() for identifier in model_identifiers]
        validated_extra_settings = validate_provider_settings(
            provider_type,
            api_key,
            extra_settings,
            model_identifiers,
            require_credentials=True,
        )
        settings_override = dict(validated_extra_settings)
        settings_override["api_key"] = api_key
        settings_override["models"] = model_identifiers
        secret_values = cls._secret_values(api_key, validated_extra_settings)
        return [
            cls._test_model(
                provider_type,
                model_identifier,
                settings_override,
                secret_values,
            )
            for model_identifier in model_identifiers
        ]

    @staticmethod
    def _secret_values(api_key: str, extra_settings: dict[str, Any]) -> list[str]:
        return [api_key] + [
            value for value in extra_settings.values() if isinstance(value, str)
        ]

    @staticmethod
    def _sanitize_test_error(exc: Exception, secret_values: list[str]) -> str:
        message = get_user_friendly_error_message(exc)
        for value in secret_values:
            if value:
                message = message.replace(value, "[redacted]")
        return message[:1000]
