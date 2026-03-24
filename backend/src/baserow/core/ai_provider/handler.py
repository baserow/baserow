from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from baserow.core.ai_provider.constants import (
    SCOPE_APPLICATION,
    SCOPE_INSTANCE,
    SCOPE_WORKSPACE,
    TEST_STATUS_FAILURE,
    TEST_STATUS_SUCCESS,
)
from baserow.core.ai_provider.exceptions import (
    AIProviderDoesNotExist,
    AIProviderModelDoesNotExist,
)
from baserow.core.ai_provider.models import (
    AIFeatureDefaultModel,
    AIProviderConfig,
    AIProviderModel,
    AIProviderModelFeature,
    AIProviderOverride,
)


class AIProviderHandler:
    @classmethod
    def _get_scope_ct_and_id(
        cls, scope_type: str, scope_id: Optional[int] = None
    ) -> tuple[Optional[ContentType], Optional[int]]:
        """
        Resolve a scope string + id to ContentType + object_id.
        Returns (None, None) for instance scope.
        """

        if scope_type == SCOPE_INSTANCE:
            return None, None
        elif scope_type == SCOPE_WORKSPACE:
            from baserow.core.models import Workspace

            ct = ContentType.objects.get_for_model(Workspace)
            return ct, scope_id
        elif scope_type == SCOPE_APPLICATION:
            from baserow.core.models import Application

            ct = ContentType.objects.get_for_model(Application)
            return ct, scope_id
        else:
            raise ValueError(f"Unknown scope type: {scope_type}")

    @classmethod
    def get_provider(cls, provider_id: int) -> AIProviderConfig:
        try:
            return AIProviderConfig.objects.get(id=provider_id)
        except AIProviderConfig.DoesNotExist:
            raise AIProviderDoesNotExist(
                f"AI provider config with id {provider_id} does not exist."
            )

    @classmethod
    def get_provider_model(cls, model_id: int) -> AIProviderModel:
        try:
            return AIProviderModel.objects.select_related("provider_config").get(
                id=model_id
            )
        except AIProviderModel.DoesNotExist:
            raise AIProviderModelDoesNotExist(
                f"AI provider model with id {model_id} does not exist."
            )

    @classmethod
    def list_providers(
        cls, scope_type: str, scope_id: Optional[int] = None
    ) -> list[AIProviderConfig]:
        """
        List providers defined at exactly the given scope (not inherited).
        """

        ct, obj_id = cls._get_scope_ct_and_id(scope_type, scope_id)
        return list(
            AIProviderConfig.objects.filter(
                scope_content_type=ct, scope_object_id=obj_id
            ).prefetch_related("models", "models__features")
        )

    @classmethod
    def list_effective_providers(
        cls, scope_type: str, scope_id: Optional[int] = None
    ) -> list[dict]:
        """
        Return the merged list of providers visible at the given scope.
        Each entry includes `is_own_scope` (whether it belongs to this scope
        or is inherited) and `is_enabled` (whether it's enabled, considering
        overrides).

        Resolution for workspace scope:
          1. Instance-level providers (with workspace overrides applied)
          2. Workspace-level providers

        Resolution for application scope:
          1. Instance-level providers (with app overrides applied)
          2. Workspace-level providers (with app overrides applied)
          3. Application-level providers
        """

        ct, obj_id = cls._get_scope_ct_and_id(scope_type, scope_id)
        result = []

        # Build the override lookup for this scope
        overrides = {}
        if ct is not None:
            for override in AIProviderOverride.objects.filter(
                scope_content_type=ct, scope_object_id=obj_id
            ):
                overrides[override.provider_config_id] = override.is_enabled

        # Collect providers from parent scopes (inherited)
        parent_scopes = cls._get_parent_scopes(scope_type, scope_id)
        for parent_ct, parent_obj_id in parent_scopes:
            providers = AIProviderConfig.objects.filter(
                scope_content_type=parent_ct, scope_object_id=parent_obj_id
            ).prefetch_related("models", "models__features")
            for provider in providers:
                is_enabled = overrides.get(provider.id, provider.is_active)
                result.append(
                    {
                        "provider": provider,
                        "is_own_scope": False,
                        "is_enabled": is_enabled,
                    }
                )

        # Add own-scope providers
        own_providers = AIProviderConfig.objects.filter(
            scope_content_type=ct, scope_object_id=obj_id
        ).prefetch_related("models", "models__features")
        for provider in own_providers:
            result.append(
                {
                    "provider": provider,
                    "is_own_scope": True,
                    "is_enabled": provider.is_active,
                }
            )

        return result

    @classmethod
    def _get_parent_scopes(
        cls, scope_type: str, scope_id: Optional[int] = None
    ) -> list[tuple[Optional[ContentType], Optional[int]]]:
        """
        Return parent scope (ct, obj_id) pairs for a given scope,
        ordered from most distant ancestor to nearest parent.
        """

        if scope_type == SCOPE_INSTANCE:
            return []
        elif scope_type == SCOPE_WORKSPACE:
            # Instance is the only parent of workspace
            return [(None, None)]
        elif scope_type == SCOPE_APPLICATION:
            # Parents: instance, then the application's workspace
            from baserow.core.models import Application

            try:
                app = Application.objects.get(id=scope_id)
                workspace_ct = ContentType.objects.get_for_model(app.workspace)
                return [(None, None), (workspace_ct, app.workspace_id)]
            except Application.DoesNotExist:
                return [(None, None)]
        return []

    @classmethod
    @transaction.atomic
    def create_provider(
        cls,
        user,
        provider_type: str,
        name: str,
        scope_type: str,
        scope_id: Optional[int] = None,
        api_key: str = "",
        extra_settings: Optional[dict] = None,
        is_active: bool = True,
        models_data: Optional[list[dict]] = None,
    ) -> AIProviderConfig:
        """
        Create a new AI provider config at the given scope.

        :param models_data: List of dicts with keys:
            model_identifier, display_name (optional), is_enabled (optional),
            features (optional, list of feature_type strings)
        """

        ct, obj_id = cls._get_scope_ct_and_id(scope_type, scope_id)

        provider = AIProviderConfig.objects.create(
            provider_type=provider_type,
            name=name,
            api_key=api_key,
            extra_settings=extra_settings or {},
            scope_content_type=ct,
            scope_object_id=obj_id,
            created_by=user,
            is_active=is_active,
        )

        if models_data:
            cls._sync_models(provider, models_data)

        return provider

    @classmethod
    @transaction.atomic
    def update_provider(
        cls,
        user,
        provider: AIProviderConfig,
        **values,
    ) -> AIProviderConfig:
        """
        Update an AI provider config. `models_data` replaces all models
        if provided (full replacement, not merge).
        """

        allowed_fields = {"name", "api_key", "extra_settings", "is_active"}
        models_data = values.pop("models_data", None)

        for key, value in values.items():
            if key in allowed_fields:
                setattr(provider, key, value)
        provider.save()

        if models_data is not None:
            cls._sync_models(provider, models_data)

        return provider

    @classmethod
    @transaction.atomic
    def delete_provider(cls, user, provider: AIProviderConfig):
        provider.delete()

    @classmethod
    def _sync_models(cls, provider: AIProviderConfig, models_data: list[dict]):
        """
        Sync models for a provider. Matches existing models by identifier
        to preserve test status and IDs. Removes models not in the new list,
        creates new ones, and updates features for all.
        """

        existing = {m.model_identifier: m for m in provider.models.all()}
        seen_identifiers = set()

        for order, model_data in enumerate(models_data):
            identifier = model_data["model_identifier"]
            features = model_data.get("features", [])
            seen_identifiers.add(identifier)

            if identifier in existing:
                # Update existing model — preserve test status
                provider_model = existing[identifier]
                provider_model.display_name = model_data.get("display_name", "")
                provider_model.is_enabled = model_data.get("is_enabled", True)
                provider_model.order = order
                provider_model.save(
                    update_fields=["display_name", "is_enabled", "order"]
                )
            else:
                # Create new model
                provider_model = AIProviderModel.objects.create(
                    provider_config=provider,
                    model_identifier=identifier,
                    display_name=model_data.get("display_name", ""),
                    is_enabled=model_data.get("is_enabled", True),
                    order=order,
                )

            # Sync features for this model
            current_features = set(
                provider_model.features.values_list("feature_type", flat=True)
            )
            desired_features = set(features)

            # Remove features no longer desired
            if current_features - desired_features:
                provider_model.features.filter(
                    feature_type__in=current_features - desired_features
                ).delete()

            # Add new features
            for feature_type in desired_features - current_features:
                AIProviderModelFeature.objects.create(
                    provider_model=provider_model,
                    feature_type=feature_type,
                )

        # Delete models that are no longer in the list
        to_delete = set(existing.keys()) - seen_identifiers
        if to_delete:
            provider.models.filter(model_identifier__in=to_delete).delete()

    @classmethod
    @transaction.atomic
    def toggle_provider_override(
        cls,
        user,
        provider: AIProviderConfig,
        scope_type: str,
        scope_id: int,
        is_enabled: bool,
    ) -> AIProviderOverride:
        """
        Create or update an override for an inherited provider at a child scope.
        """

        ct, obj_id = cls._get_scope_ct_and_id(scope_type, scope_id)
        override, _ = AIProviderOverride.objects.update_or_create(
            provider_config=provider,
            scope_content_type=ct,
            scope_object_id=obj_id,
            defaults={"is_enabled": is_enabled},
        )
        return override

    @classmethod
    def get_available_models_for_feature(
        cls,
        feature_type: str,
        scope_type: str,
        scope_id: Optional[int] = None,
    ) -> list[AIProviderModel]:
        """
        Return all enabled models for a given feature at a given scope,
        resolving the full hierarchy with overrides.
        """

        effective = cls.list_effective_providers(scope_type, scope_id)
        models = []
        for entry in effective:
            if not entry["is_enabled"]:
                continue
            provider = entry["provider"]
            for model in provider.models.all():
                if not model.is_enabled:
                    continue
                feature_types = {f.feature_type for f in model.features.all()}
                if feature_type in feature_types:
                    models.append(model)
        return models

    @classmethod
    def get_feature_default_model(
        cls,
        feature_type: str,
        scope_type: str,
        scope_id: Optional[int] = None,
    ) -> Optional[AIProviderModel]:
        """
        Resolve the default model for a feature at a scope.
        Resolution: check scope → check parent scopes → None.
        """

        ct, obj_id = cls._get_scope_ct_and_id(scope_type, scope_id)

        # Check this scope first
        default = (
            AIFeatureDefaultModel.objects.filter(
                feature_type=feature_type,
                scope_content_type=ct,
                scope_object_id=obj_id,
            )
            .select_related("provider_model", "provider_model__provider_config")
            .first()
        )

        if default:
            return default.provider_model

        # Walk up parent scopes
        parent_scopes = cls._get_parent_scopes(scope_type, scope_id)
        for parent_ct, parent_obj_id in reversed(parent_scopes):
            default = (
                AIFeatureDefaultModel.objects.filter(
                    feature_type=feature_type,
                    scope_content_type=parent_ct,
                    scope_object_id=parent_obj_id,
                )
                .select_related("provider_model", "provider_model__provider_config")
                .first()
            )
            if default:
                return default.provider_model

        return None

    @classmethod
    @transaction.atomic
    def set_feature_default_model(
        cls,
        user,
        feature_type: str,
        provider_model: AIProviderModel,
        scope_type: str,
        scope_id: Optional[int] = None,
    ) -> AIFeatureDefaultModel:
        ct, obj_id = cls._get_scope_ct_and_id(scope_type, scope_id)
        default, _ = AIFeatureDefaultModel.objects.update_or_create(
            feature_type=feature_type,
            scope_content_type=ct,
            scope_object_id=obj_id,
            defaults={"provider_model": provider_model},
        )
        return default

    @classmethod
    def test_model(cls, user, provider_model: AIProviderModel) -> AIProviderModel:
        """
        Test a specific model by sending a minimal prompt using the parent
        provider's API key. Updates last_test_at/status/error.
        """

        from baserow.core.generative_ai.registries import (
            generative_ai_model_type_registry,
        )

        config = provider_model.provider_config
        now = timezone.now()

        try:
            model_type = generative_ai_model_type_registry.get(config.provider_type)

            # Build a settings_override dict from the AIProviderConfig
            settings_override = {"api_key": config.api_key}
            settings_override.update(config.extra_settings)
            settings_override["models"] = [provider_model.model_identifier]

            model_type.prompt(
                model=provider_model.model_identifier,
                prompt="Reply with the single word: ok",
                workspace=None,
                temperature=0,
                settings_override=settings_override,
            )
            provider_model.last_test_at = now
            provider_model.last_test_status = TEST_STATUS_SUCCESS
            provider_model.last_test_error = ""
        except Exception as exc:
            provider_model.last_test_at = now
            provider_model.last_test_status = TEST_STATUS_FAILURE
            provider_model.last_test_error = str(exc)

        provider_model.save(
            update_fields=[
                "last_test_at",
                "last_test_status",
                "last_test_error",
            ]
        )
        return provider_model
