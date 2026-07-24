from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.core.handler import CoreHandler

from .handler import AIProviderHandler
from .models import AIProviderConfig, AIProviderModel
from .operations import ManageAIProvidersOperationType
from .provider_types import get_provider_type_metadata
from .signals import ai_provider_availability_changed, ai_provider_changed


class AIProviderService:
    @staticmethod
    def _check_permissions(user: AbstractUser) -> None:
        CoreHandler().check_permissions(
            user, ManageAIProvidersOperationType.type, context=None
        )

    @staticmethod
    def _send_availability_changed(
        user: AbstractUser,
        provider_type: str,
        model_identifiers: set[str] | None = None,
    ) -> None:
        ai_provider_availability_changed.send(
            AIProviderService,
            user=user,
            provider_type=provider_type,
            model_identifiers=model_identifiers,
        )

    @staticmethod
    def _send_changed(user: AbstractUser, workspace_models_changed: bool) -> None:
        ai_provider_changed.send(
            AIProviderService,
            user=user,
            workspace_models_changed=workspace_models_changed,
        )

    @classmethod
    def list_providers(cls, user: AbstractUser) -> QuerySet[AIProviderConfig]:
        cls._check_permissions(user)
        return AIProviderHandler.list_providers()

    @classmethod
    def list_provider_types(cls, user: AbstractUser) -> list[dict[str, Any]]:
        cls._check_permissions(user)
        return get_provider_type_metadata()

    @classmethod
    def create_provider(cls, user: AbstractUser, **values) -> AIProviderConfig:
        cls._check_permissions(user)
        provider = AIProviderHandler.create_provider(**values)
        cls._send_changed(user, workspace_models_changed=True)
        cls._send_availability_changed(user, provider.provider_type)
        return provider

    @classmethod
    def update_provider(
        cls,
        user: AbstractUser,
        provider_id: int,
        **values,
    ) -> AIProviderConfig:
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        was_active = provider.is_active
        provider = AIProviderHandler.update_provider(provider, **values)
        workspace_models_changed = provider.is_active != was_active
        cls._send_changed(user, workspace_models_changed)
        if workspace_models_changed:
            cls._send_availability_changed(user, provider.provider_type)
        return provider

    @classmethod
    def delete_provider(cls, user: AbstractUser, provider_id: int) -> None:
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        provider_type = provider.provider_type
        AIProviderHandler.delete_provider(provider)
        cls._send_changed(user, workspace_models_changed=True)
        cls._send_availability_changed(user, provider_type)

    @classmethod
    def create_model(
        cls, user: AbstractUser, provider_id: int, **values
    ) -> AIProviderModel:
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        model = AIProviderHandler.create_model(provider, **values)
        cls._send_changed(user, workspace_models_changed=True)
        cls._send_availability_changed(
            user, provider.provider_type, {model.model_identifier}
        )
        return model

    @classmethod
    def discover_models(
        cls,
        user: AbstractUser,
        provider_type: str,
    ) -> list[str] | None:
        cls._check_permissions(user)
        return AIProviderHandler.discover_models(provider_type)

    @classmethod
    def update_model(
        cls,
        user: AbstractUser,
        model_id: int,
        **values,
    ) -> AIProviderModel:
        cls._check_permissions(user)
        model = AIProviderHandler.get_model(model_id)
        provider_type = model.provider_config.provider_type
        old_identifier = model.model_identifier
        was_enabled = model.is_enabled
        model = AIProviderHandler.update_model(model, **values)
        workspace_models_changed = (
            model.model_identifier != old_identifier or model.is_enabled != was_enabled
        )
        cls._send_changed(user, workspace_models_changed)
        if workspace_models_changed:
            cls._send_availability_changed(
                user,
                provider_type,
                {old_identifier, model.model_identifier},
            )
        return model

    @classmethod
    def delete_model(cls, user: AbstractUser, model_id: int) -> None:
        cls._check_permissions(user)
        model = AIProviderHandler.get_model(model_id)
        provider_type = model.provider_config.provider_type
        model_identifier = model.model_identifier
        AIProviderHandler.delete_model(model)
        cls._send_changed(user, workspace_models_changed=True)
        cls._send_availability_changed(user, provider_type, {model_identifier})

    @classmethod
    def test_models(
        cls, user: AbstractUser, model_ids: list[int]
    ) -> list[dict[str, Any]]:
        cls._check_permissions(user)
        results = AIProviderHandler.test_models(AIProviderHandler.get_models(model_ids))
        cls._send_changed(user, workspace_models_changed=False)
        return results
