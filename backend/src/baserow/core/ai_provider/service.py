from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.core.handler import CoreHandler

from .handler import AIProviderHandler
from .models import AIProviderConfig, AIProviderModel
from .operations import ManageAIProvidersOperationType
from .provider_types import get_provider_type_metadata


class AIProviderService:
    @staticmethod
    def _check_permissions(user: AbstractUser) -> None:
        CoreHandler().check_permissions(
            user, ManageAIProvidersOperationType.type, context=None
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
        return AIProviderHandler.create_provider(**values)

    @classmethod
    def update_provider(
        cls,
        user: AbstractUser,
        provider_id: int,
        **values,
    ) -> AIProviderConfig:
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        return AIProviderHandler.update_provider(provider, **values)

    @classmethod
    def delete_provider(cls, user: AbstractUser, provider_id: int) -> None:
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        AIProviderHandler.delete_provider(provider)

    @classmethod
    def create_model(
        cls, user: AbstractUser, provider_id: int, **values
    ) -> AIProviderModel:
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        return AIProviderHandler.create_model(provider, **values)

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
        return AIProviderHandler.update_model(model, **values)

    @classmethod
    def delete_model(cls, user: AbstractUser, model_id: int) -> None:
        cls._check_permissions(user)
        model = AIProviderHandler.get_model(model_id)
        AIProviderHandler.delete_model(model)

    @classmethod
    def test_models(
        cls, user: AbstractUser, model_ids: list[int]
    ) -> list[dict[str, Any]]:
        cls._check_permissions(user)
        return AIProviderHandler.test_models(AIProviderHandler.get_models(model_ids))
