from baserow.core.handler import CoreHandler

from .handler import AIProviderHandler
from .operations import ManageAIProvidersOperationType


class AIProviderService:
    @staticmethod
    def _check_permissions(user):
        CoreHandler().check_permissions(
            user, ManageAIProvidersOperationType.type, context=None
        )

    @classmethod
    def check_permissions(cls, user):
        cls._check_permissions(user)

    @classmethod
    def list_providers(cls, user):
        cls._check_permissions(user)
        return AIProviderHandler.list_providers()

    @classmethod
    def create_provider(cls, user, **values):
        cls._check_permissions(user)
        return AIProviderHandler.create_provider(**values)

    @classmethod
    def update_provider(
        cls,
        user,
        provider_id: int,
        **values,
    ):
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        return AIProviderHandler.update_provider(provider, **values)

    @classmethod
    def delete_provider(cls, user, provider_id: int):
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        AIProviderHandler.delete_provider(provider)

    @classmethod
    def create_model(cls, user, provider_id: int, **values):
        cls._check_permissions(user)
        provider = AIProviderHandler.get_provider(provider_id)
        return AIProviderHandler.create_model(provider, **values)

    @classmethod
    def discover_models(
        cls,
        user,
        provider_type: str,
    ) -> list[str] | None:
        cls._check_permissions(user)
        return AIProviderHandler.discover_models(provider_type)

    @classmethod
    def update_model(
        cls,
        user,
        model_id: int,
        **values,
    ):
        cls._check_permissions(user)
        model = AIProviderHandler.get_model(model_id)
        return AIProviderHandler.update_model(model, **values)

    @classmethod
    def delete_model(cls, user, model_id: int):
        cls._check_permissions(user)
        model = AIProviderHandler.get_model(model_id)
        AIProviderHandler.delete_model(model)

    @classmethod
    def test_models(cls, user, model_ids: list[int]):
        cls._check_permissions(user)
        return AIProviderHandler.test_models(AIProviderHandler.get_models(model_ids))
