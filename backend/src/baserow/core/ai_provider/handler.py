from typing import Any

from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone

from baserow.core.cache import local_cache
from baserow.core.generative_ai.exceptions import get_user_friendly_error_message
from baserow.core.models import Workspace
from baserow.core.psycopg import is_unique_violation_error

from .constants import (
    AI_PROVIDER_CONFIGS_LOCAL_CACHE_KEY,
    AI_PROVIDER_TEST_MAX_TOKENS,
    AI_PROVIDER_TEST_STATUS_FAILURE,
    AI_PROVIDER_TEST_STATUS_SUCCESS,
    PROVIDER_ENVIRONMENT_SETTINGS,
)
from .exceptions import (
    AIProviderDoesNotExist,
    AIProviderModelAlreadyConfigured,
    AIProviderModelDoesNotExist,
    AIProviderTypeAlreadyConfigured,
)
from .models import (
    AIProviderConfig,
    AIProviderModel,
    AIProviderWorkspaceOverride,
)
from .provider_types import (
    get_supported_provider_type,
    validate_provider_settings,
)


class AIProviderHandler:
    @staticmethod
    def _invalidate_resolution_cache() -> None:
        local_cache.delete(f"{AI_PROVIDER_CONFIGS_LOCAL_CACHE_KEY}*")

    @staticmethod
    def _decorate_provider(
        provider: AIProviderConfig,
        workspace: Workspace | None,
        workspace_enabled: bool = True,
    ) -> AIProviderConfig:
        inherited = workspace is not None and provider.workspace_id is None
        provider.workspace_enabled = workspace_enabled
        provider.source_is_active = provider.is_active
        provider.effective_is_active = provider.is_active and workspace_enabled
        provider.read_only = inherited
        return provider

    @classmethod
    def list_providers(
        cls, workspace: Workspace | None = None
    ) -> list[AIProviderConfig]:
        queryset = AIProviderConfig.objects.prefetch_related("models").order_by("id")
        if workspace is None:
            return [
                cls._decorate_provider(provider, None)
                for provider in queryset.filter(workspace__isnull=True)
            ]

        scoped_providers = list(
            queryset.filter(Q(workspace=workspace) | Q(workspace__isnull=True))
        )
        owned = [
            provider
            for provider in scoped_providers
            if provider.workspace_id == workspace.id
        ]
        inherited = [
            provider for provider in scoped_providers if provider.workspace_id is None
        ]
        disabled_provider_ids = set(
            AIProviderWorkspaceOverride.objects.filter(
                workspace=workspace,
                provider_config_id__in=[provider.id for provider in inherited],
            ).values_list("provider_config_id", flat=True)
        )
        providers = [
            cls._decorate_provider(provider, workspace) for provider in owned
        ] + [
            cls._decorate_provider(
                provider, workspace, provider.id not in disabled_provider_ids
            )
            for provider in inherited
        ]
        return sorted(providers, key=lambda provider: provider.id)

    @classmethod
    def get_provider(
        cls,
        provider_id: int,
        workspace: Workspace | None = None,
        include_inherited: bool = False,
    ) -> AIProviderConfig:
        scope = Q(workspace__isnull=True)
        if workspace is not None:
            scope = Q(workspace=workspace)
            if include_inherited:
                scope |= Q(workspace__isnull=True)
        try:
            provider = AIProviderConfig.objects.prefetch_related("models").get(
                scope, id=provider_id
            )
        except AIProviderConfig.DoesNotExist as exc:
            raise AIProviderDoesNotExist(provider_id) from exc
        workspace_enabled = True
        if workspace is not None and provider.workspace_id is None:
            workspace_enabled = not AIProviderWorkspaceOverride.objects.filter(
                workspace=workspace, provider_config=provider
            ).exists()
        return cls._decorate_provider(provider, workspace, workspace_enabled)

    @staticmethod
    def get_model(
        model_id: int,
        workspace: Workspace | None = None,
        include_inherited: bool = False,
    ) -> AIProviderModel:
        scope = Q(provider_config__workspace__isnull=True)
        if workspace is not None:
            scope = Q(provider_config__workspace=workspace)
            if include_inherited:
                scope |= Q(provider_config__workspace__isnull=True)
        try:
            return AIProviderModel.objects.select_related("provider_config").get(
                scope, id=model_id
            )
        except AIProviderModel.DoesNotExist as exc:
            raise AIProviderModelDoesNotExist(model_id) from exc

    @staticmethod
    def get_models(
        model_ids: list[int],
        workspace: Workspace | None = None,
        include_inherited: bool = False,
    ) -> list[AIProviderModel]:
        scope = Q(provider_config__workspace__isnull=True)
        if workspace is not None:
            scope = Q(provider_config__workspace=workspace)
            if include_inherited:
                scope |= Q(provider_config__workspace__isnull=True)
        models_by_id = {
            model.id: model
            for model in AIProviderModel.objects.filter(scope, id__in=model_ids)
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
        workspace: Workspace | None = None,
    ) -> AIProviderConfig:
        get_supported_provider_type(provider_type)
        if AIProviderConfig.objects.filter(
            workspace=workspace, provider_type=provider_type
        ).exists():
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
                workspace=workspace,
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
        return cls.get_provider(provider.id, workspace=workspace)

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
        return cls.get_provider(provider.id, workspace=provider.workspace)

    @staticmethod
    def delete_provider(provider: AIProviderConfig) -> None:
        workspace = provider.workspace
        provider_type = provider.provider_type
        provider.delete()
        if workspace is not None:
            legacy_settings = dict(workspace.generative_ai_models_settings or {})
            if legacy_settings.pop(provider_type, None) is not None:
                workspace.generative_ai_models_settings = legacy_settings
                workspace.save(update_fields=("generative_ai_models_settings",))
        AIProviderHandler._invalidate_resolution_cache()

    @classmethod
    def set_workspace_provider_enabled(
        cls,
        workspace: Workspace,
        provider: AIProviderConfig,
        is_enabled: bool,
    ) -> AIProviderConfig:
        if is_enabled:
            AIProviderWorkspaceOverride.objects.filter(
                workspace=workspace, provider_config=provider
            ).delete()
        else:
            AIProviderWorkspaceOverride.objects.get_or_create(
                workspace=workspace,
                provider_config=provider,
            )
        cls._invalidate_resolution_cache()
        return cls.get_provider(
            provider.id, workspace=workspace, include_inherited=True
        )

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
            require_credentials=True,
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
            require_credentials=True,
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
        return cls.get_model(model.id, workspace=model.provider_config.workspace)

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
        model_id: int,
    ) -> dict[str, Any]:
        model_type = get_supported_provider_type(provider_type)
        try:
            model_type.prompt(
                model_identifier,
                "OK",
                settings_override=settings_override,
                model_settings_override={"max_tokens": AI_PROVIDER_TEST_MAX_TOKENS},
            )
        except Exception as exc:
            status = AI_PROVIDER_TEST_STATUS_FAILURE
            error = cls._sanitize_test_error(exc, secret_values)
        else:
            status = AI_PROVIDER_TEST_STATUS_SUCCESS
            error = ""

        return {
            "model_id": model_id,
            "status": status,
            "error": error,
            "tested_at": timezone.now(),
        }

    @classmethod
    def test_models(cls, models: list[AIProviderModel]) -> list[dict[str, Any]]:
        results = []
        for model in models:
            provider = model.provider_config
            settings_override = {
                name: provider.extra_settings.get(name)
                for name in PROVIDER_ENVIRONMENT_SETTINGS[provider.provider_type][
                    "extra_settings"
                ]
            }
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

    @staticmethod
    def _secret_values(api_key: str, extra_settings: dict[str, Any]) -> list[str]:
        return [api_key] + [
            value for value in extra_settings.values() if isinstance(value, str)
        ]

    @staticmethod
    def _sanitize_test_error(exc: Exception, secret_values: list[str]) -> str:
        message = get_user_friendly_error_message(exc)
        # Replace longer overlapping secrets first. Otherwise replacing a short
        # secret can leave the remainder of a longer secret visible.
        for value in sorted(
            {value for value in secret_values if value}, key=len, reverse=True
        ):
            message = message.replace(value, "[redacted]")
        return message[:1000]
