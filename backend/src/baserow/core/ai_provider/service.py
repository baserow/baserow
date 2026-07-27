from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.operations import UpdateWorkspaceOperationType

from .exceptions import AIProviderIsReadOnly
from .handler import AIProviderHandler
from .models import AIProviderConfig, AIProviderModel
from .operations import ManageAIProvidersOperationType
from .provider_types import get_provider_type_metadata
from .signals import ai_provider_updated


class AIProviderService:
    @staticmethod
    def _check_permissions(
        user: AbstractUser, workspace_id: int | None = None
    ) -> Workspace | None:
        handler = CoreHandler()
        if workspace_id is None:
            handler.check_permissions(
                user, ManageAIProvidersOperationType.type, context=None
            )
            return None
        workspace = handler.get_workspace(workspace_id)
        handler.check_permissions(
            user,
            UpdateWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        return workspace

    @staticmethod
    def _send_updated(
        user: AbstractUser,
        workspace: Workspace | None,
        model_availability_updated: bool,
        provider_type: str | None = None,
        model_identifiers: set[str] | None = None,
    ) -> None:
        ai_provider_updated.send(
            AIProviderService,
            user=user,
            workspace=workspace,
            model_availability_updated=model_availability_updated,
            provider_type=provider_type,
            model_identifiers=model_identifiers,
        )

    @classmethod
    def list_providers(
        cls, user: AbstractUser, workspace_id: int | None = None
    ) -> list[AIProviderConfig]:
        workspace = cls._check_permissions(user, workspace_id)
        return AIProviderHandler.list_providers(workspace)

    @classmethod
    def list_provider_types(
        cls, user: AbstractUser, workspace_id: int | None = None
    ) -> list[dict[str, Any]]:
        cls._check_permissions(user, workspace_id)
        return get_provider_type_metadata()

    @classmethod
    def create_provider(
        cls, user: AbstractUser, workspace_id: int | None = None, **values
    ) -> AIProviderConfig:
        workspace = cls._check_permissions(user, workspace_id)
        provider = AIProviderHandler.create_provider(workspace=workspace, **values)
        cls._send_updated(user, workspace, True, provider.provider_type)
        return provider

    @classmethod
    def update_provider(
        cls,
        user: AbstractUser,
        provider_id: int,
        workspace_id: int | None = None,
        **values,
    ) -> AIProviderConfig:
        workspace = cls._check_permissions(user, workspace_id)
        provider = AIProviderHandler.get_provider(
            provider_id,
            workspace=workspace,
            include_inherited=workspace is not None,
        )
        if workspace is not None and provider.workspace_id is None:
            if set(values) != {"is_active"}:
                raise AIProviderIsReadOnly(provider_id)
            provider = AIProviderHandler.set_workspace_provider_enabled(
                workspace, provider, values["is_active"]
            )
            cls._send_updated(user, workspace, True, provider.provider_type)
            return provider

        was_active = provider.is_active
        provider = AIProviderHandler.update_provider(provider, **values)
        model_availability_updated = provider.is_active != was_active
        cls._send_updated(
            user,
            workspace,
            model_availability_updated,
            provider.provider_type,
        )
        return provider

    @classmethod
    def delete_provider(
        cls,
        user: AbstractUser,
        provider_id: int,
        workspace_id: int | None = None,
    ) -> None:
        workspace = cls._check_permissions(user, workspace_id)
        provider = AIProviderHandler.get_provider(
            provider_id,
            workspace=workspace,
            include_inherited=workspace is not None,
        )
        if workspace is not None and provider.workspace_id is None:
            raise AIProviderIsReadOnly(provider_id)
        provider_type = provider.provider_type
        workspace = AIProviderHandler.delete_provider(provider)
        cls._send_updated(user, workspace, True, provider_type)

    @classmethod
    def create_model(
        cls,
        user: AbstractUser,
        provider_id: int,
        workspace_id: int | None = None,
        **values,
    ) -> AIProviderModel:
        workspace = cls._check_permissions(user, workspace_id)
        provider = AIProviderHandler.get_provider(provider_id, workspace=workspace)
        model = AIProviderHandler.create_model(provider, **values)
        cls._send_updated(
            user,
            workspace,
            True,
            provider.provider_type,
            {model.model_identifier},
        )
        return model

    @classmethod
    def discover_models(
        cls,
        user: AbstractUser,
        provider_type: str,
        workspace_id: int | None = None,
    ) -> list[str] | None:
        cls._check_permissions(user, workspace_id)
        return AIProviderHandler.discover_models(provider_type)

    @classmethod
    def update_model(
        cls,
        user: AbstractUser,
        model_id: int,
        workspace_id: int | None = None,
        **values,
    ) -> AIProviderModel:
        workspace = cls._check_permissions(user, workspace_id)
        model = AIProviderHandler.get_model(model_id, workspace=workspace)
        provider_type = model.provider_config.provider_type
        old_identifier = model.model_identifier
        was_enabled = model.is_enabled
        model = AIProviderHandler.update_model(model, **values)
        model_availability_updated = (
            model.model_identifier != old_identifier or model.is_enabled != was_enabled
        )
        cls._send_updated(
            user,
            workspace,
            model_availability_updated,
            provider_type,
            {old_identifier, model.model_identifier},
        )
        return model

    @classmethod
    def delete_model(
        cls,
        user: AbstractUser,
        model_id: int,
        workspace_id: int | None = None,
    ) -> None:
        workspace = cls._check_permissions(user, workspace_id)
        model = AIProviderHandler.get_model(model_id, workspace=workspace)
        provider_type = model.provider_config.provider_type
        model_identifier = model.model_identifier
        AIProviderHandler.delete_model(model)
        cls._send_updated(user, workspace, True, provider_type, {model_identifier})

    @classmethod
    def test_models(
        cls,
        user: AbstractUser,
        model_ids: list[int],
        workspace_id: int | None = None,
    ) -> list[dict[str, Any]]:
        workspace = cls._check_permissions(user, workspace_id)
        # A test prompt uses the selected provider's credentials and overwrites
        # that model's own result.
        models = AIProviderHandler.get_models(model_ids, workspace=workspace)
        results = AIProviderHandler.test_models(models)
        cls._send_updated(user, workspace, False)
        return results
