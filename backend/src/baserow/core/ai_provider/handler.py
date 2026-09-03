from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError
from django.db.models import Prefetch, Q, prefetch_related_objects
from django.utils import timezone

from baserow.core.generative_ai.capabilities import (
    ModelTextResponseNotSupportedError,
    ModelToolCallingNotSupportedError,
    test_model_text_and_tool_calling,
)
from baserow.core.generative_ai.exceptions import get_user_friendly_error_message
from baserow.core.models import Workspace
from baserow.core.psycopg import is_unique_violation_error

from .constants import (
    AI_PROVIDER_FEATURE_AI_FIELDS,
    AI_PROVIDER_FEATURE_MODE_DISABLED,
    AI_PROVIDER_FEATURE_MODE_INHERIT,
    AI_PROVIDER_FEATURE_MODE_LEGACY,
    AI_PROVIDER_FEATURE_MODE_MODEL,
    AI_PROVIDER_MODEL_CAPABILITY_TEXT,
    AI_PROVIDER_MODEL_CAPABILITY_TOOLS,
    AI_PROVIDER_TEST_MAX_TOKENS,
    AI_PROVIDER_TEST_STATUS_FAILURE,
    AI_PROVIDER_TEST_STATUS_SUCCESS,
    AI_PROVIDER_TEST_TIMEOUT_SECONDS,
    AI_PROVIDER_TYPES,
)
from .exceptions import (
    AIProviderDoesNotExist,
    AIProviderFeatureModelNotAvailable,
    AIProviderFeatureModeNotAllowed,
    AIProviderModelAlreadyConfigured,
    AIProviderModelDoesNotExist,
    AIProviderModelInUse,
    AIProviderTypeAlreadyConfigured,
)
from .models import (
    AIProviderConfig,
    AIProviderFeatureSetting,
    AIProviderModel,
    AIProviderWorkspaceOverride,
)
from .provider_types import (
    get_supported_provider_type,
    validate_provider_settings,
)
from .registries import ai_provider_model_feature_type_registry
from .resolution import (
    ScopedAIProviderState,
    clear_ai_provider_state_cache,
    get_ai_provider_state,
)


@dataclass(frozen=True, slots=True)
class WorkspaceAIProviderConfig:
    """The explicit, workspace-scoped representation of an AI provider."""

    id: int
    provider_type: str
    extra_settings: dict[str, Any]
    is_active: bool
    models: list[AIProviderModel]
    workspace_enabled: bool
    read_only: bool


class AIProviderHandler:
    @staticmethod
    def _normalize_feature_types(feature_types: list[str] | None) -> list[str]:
        if feature_types is None:
            # Older API callers predate per-feature model eligibility. Preserve
            # their AI Fields-only behaviour instead of silently opting models
            # into every feature registered by the running installation.
            return [AI_PROVIDER_FEATURE_AI_FIELDS]

        normalized = list(dict.fromkeys(feature_types))
        for feature_type in normalized:
            ai_provider_model_feature_type_registry.get(feature_type)
        return normalized

    @staticmethod
    def _workspace_provider_config(
        provider: AIProviderConfig,
        workspace_enabled: bool = True,
        models: list[AIProviderModel] | None = None,
    ) -> WorkspaceAIProviderConfig:
        """
        Build the secret-safe provider representation used by workspace APIs.

        :param provider: The owned or inherited provider to represent.
        :param workspace_enabled: Whether an inherited provider is enabled here.
        :param models: The models to expose, when the caller already narrowed them.
        :return: The explicit workspace-scoped provider representation.
        """

        inherited = provider.workspace_id is None
        return WorkspaceAIProviderConfig(
            id=provider.id,
            provider_type=provider.provider_type,
            extra_settings={} if inherited else provider.extra_settings,
            is_active=provider.is_active and workspace_enabled,
            models=list(provider.models.all()) if models is None else models,
            workspace_enabled=workspace_enabled,
            read_only=inherited,
        )

    @classmethod
    def get_workspace_provider_config(
        cls, provider: AIProviderConfig, workspace: Workspace
    ) -> WorkspaceAIProviderConfig:
        inherited = provider.workspace_id is None
        workspace_enabled = not (
            inherited
            and AIProviderWorkspaceOverride.objects.filter(
                workspace=workspace, provider_config=provider
            ).exists()
        )
        return cls._workspace_provider_config(provider, workspace_enabled)

    @staticmethod
    def _inherited_scope() -> Q:
        """
        Instance providers a workspace is allowed to see. What the instance
        disabled stays private to the instance admin, so a workspace never
        learns it exists.
        """

        return Q(workspace__isnull=True, is_active=True)

    @staticmethod
    def _inherited_model_scope() -> Q:
        return Q(
            provider_config__workspace__isnull=True,
            provider_config__is_active=True,
            is_enabled=True,
        )

    @staticmethod
    def _models_prefetch(inherited: bool) -> Prefetch | str:
        if not inherited:
            return "models"
        return Prefetch(
            "models", queryset=AIProviderModel.objects.filter(is_enabled=True)
        )

    @classmethod
    def _inherited_providers(cls) -> list[AIProviderConfig]:
        return list(
            AIProviderConfig.objects.filter(cls._inherited_scope())
            .prefetch_related(cls._models_prefetch(True))
            .order_by("id")
        )

    @classmethod
    def list_providers(
        cls,
        workspace: Workspace | None = None,
        state: ScopedAIProviderState | None = None,
    ) -> list[AIProviderConfig | WorkspaceAIProviderConfig]:
        """
        List providers visible in an instance or workspace scope.

        :param workspace: The workspace scope, or None for the instance scope.
        :param state: An already-loaded state for the scope, avoiding a reload.
        :return: Instance providers or secret-safe workspace representations.
        """

        if state is not None:
            return cls._providers_from_state(state)

        queryset = AIProviderConfig.objects.prefetch_related("models").order_by("id")
        if workspace is None:
            return list(queryset.filter(workspace__isnull=True))

        owned = list(queryset.filter(workspace=workspace))
        inherited = cls._inherited_providers()
        disabled_provider_ids = set(
            AIProviderWorkspaceOverride.objects.filter(
                workspace=workspace,
                provider_config_id__in=[provider.id for provider in inherited],
            ).values_list("provider_config_id", flat=True)
        )
        providers = [cls._workspace_provider_config(provider) for provider in owned] + [
            cls._workspace_provider_config(
                provider, provider.id not in disabled_provider_ids
            )
            for provider in inherited
        ]
        return sorted(providers, key=lambda provider: provider.id)

    @classmethod
    def _providers_from_state(
        cls, state: ScopedAIProviderState
    ) -> list[AIProviderConfig | WorkspaceAIProviderConfig]:
        """
        Build the same visible provider list from an already-loaded scope.

        The state holds every row of the scope unfiltered, so the instance-privacy
        filters that ``_inherited_scope``/``_models_prefetch`` apply in SQL have to
        be applied here instead.

        :param state: The loaded state of the instance or workspace scope.
        :return: Instance providers or secret-safe workspace representations.
        """

        if state.workspace is None:
            return sorted(state.instance_providers.values(), key=lambda p: p.id)

        providers = [
            cls._workspace_provider_config(provider)
            for provider in state.owned_providers.values()
        ] + [
            cls._workspace_provider_config(
                provider,
                provider.id not in state.disabled_instance_provider_ids,
                models=[model for model in provider.models.all() if model.is_enabled],
            )
            for provider in state.instance_providers.values()
            if provider.is_active
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
                scope |= cls._inherited_scope()
        try:
            provider = AIProviderConfig.objects.get(scope, id=provider_id)
        except AIProviderConfig.DoesNotExist as exc:
            raise AIProviderDoesNotExist(provider_id) from exc
        inherited = workspace is not None and provider.workspace_id is None
        prefetch_related_objects([provider], cls._models_prefetch(inherited))
        return provider

    @classmethod
    def get_model(
        cls,
        model_id: int,
        workspace: Workspace | None = None,
        include_inherited: bool = False,
    ) -> AIProviderModel:
        scope = Q(provider_config__workspace__isnull=True)
        if workspace is not None:
            scope = Q(provider_config__workspace=workspace)
            if include_inherited:
                scope |= cls._inherited_model_scope()
        try:
            return AIProviderModel.objects.select_related("provider_config").get(
                scope, id=model_id
            )
        except AIProviderModel.DoesNotExist as exc:
            raise AIProviderModelDoesNotExist(model_id) from exc

    @classmethod
    def get_models(
        cls,
        model_ids: list[int],
        workspace: Workspace | None = None,
        include_inherited: bool = False,
    ) -> list[AIProviderModel]:
        scope = Q(provider_config__workspace__isnull=True)
        if workspace is not None:
            scope = Q(provider_config__workspace=workspace)
            if include_inherited:
                scope |= cls._inherited_model_scope()
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
                    "feature_types": AIProviderHandler._normalize_feature_types(
                        model.get("feature_types")
                    ),
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
        api_key = api_key.strip()
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
        clear_ai_provider_state_cache()
        return cls.get_provider(provider.id, workspace=workspace)

    @classmethod
    def update_provider(cls, provider: AIProviderConfig, **values) -> AIProviderConfig:
        api_key = values["api_key"].strip() if "api_key" in values else provider.api_key
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
        if values.get("is_active") is False:
            cls._ensure_provider_not_in_use(provider)

        connection_settings_changed = (
            "api_key" in values and api_key != provider.api_key
        ) or (
            "extra_settings" in values
            and validated_extra_settings != provider.extra_settings
        )

        allowed = {"api_key", "is_active"}
        update_fields = []
        for key, value in values.items():
            if key in allowed:
                setattr(provider, key, api_key if key == "api_key" else value)
                update_fields.append(key)
        if "extra_settings" in values:
            provider.extra_settings = validated_extra_settings
            update_fields.append("extra_settings")
        if update_fields:
            update_fields.append("updated_on")
            provider.save(update_fields=update_fields)
            if connection_settings_changed:
                provider.models.update(
                    last_test_at=None,
                    last_test_status=None,
                    last_test_error="",
                    last_test_capabilities={},
                )
        clear_ai_provider_state_cache()
        return cls.get_provider(provider.id, workspace=provider.workspace)

    @staticmethod
    def delete_provider(provider: AIProviderConfig) -> Workspace | None:
        AIProviderHandler._ensure_provider_not_in_use(provider, prune_orphans=True)
        workspace = provider.workspace
        provider_type = provider.provider_type
        provider.delete()
        if workspace is not None:
            legacy_settings = dict(workspace.generative_ai_models_settings or {})
            if legacy_settings.pop(provider_type, None) is not None:
                workspace.generative_ai_models_settings = legacy_settings
                workspace.save(update_fields=("generative_ai_models_settings",))
        clear_ai_provider_state_cache()
        return workspace

    @classmethod
    def set_workspace_provider_enabled(
        cls,
        workspace: Workspace,
        provider: AIProviderConfig,
        is_enabled: bool,
    ) -> AIProviderConfig:
        if not is_enabled:
            cls._ensure_provider_not_in_use(provider, workspace)
        if is_enabled:
            AIProviderWorkspaceOverride.objects.filter(
                workspace=workspace, provider_config=provider
            ).delete()
        else:
            AIProviderWorkspaceOverride.objects.get_or_create(
                workspace=workspace,
                provider_config=provider,
            )
        clear_ai_provider_state_cache()
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
        clear_ai_provider_state_cache()
        return model

    @classmethod
    def update_model(cls, model: AIProviderModel, **values) -> AIProviderModel:
        if "model_identifier" in values:
            values["model_identifier"] = values["model_identifier"].strip()
        model_identifier_changed = (
            "model_identifier" in values
            and values["model_identifier"] != model.model_identifier
        )
        feature_types_changed = False
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
        if "feature_types" in values:
            values["feature_types"] = cls._normalize_feature_types(
                values["feature_types"]
            )
            feature_types_changed = values["feature_types"] != model.feature_types
        if values.get("is_enabled") is False or "feature_types" in values:
            used_by = cls._feature_types_using_model(model)
            removed_used_features = used_by - set(
                values.get("feature_types", model.feature_types)
            )
            if values.get("is_enabled") is False:
                removed_used_features = used_by
            if removed_used_features:
                raise AIProviderModelInUse(
                    model.model_identifier, sorted(removed_used_features)
                )

        allowed = {"model_identifier", "is_enabled", "feature_types"}
        update_fields = []
        for key, value in values.items():
            if key in allowed:
                setattr(model, key, value)
                update_fields.append(key)
        if model_identifier_changed or feature_types_changed:
            model.last_test_at = None
            model.last_test_status = None
            model.last_test_error = ""
            model.last_test_capabilities = {}
            update_fields.extend(
                (
                    "last_test_at",
                    "last_test_status",
                    "last_test_error",
                    "last_test_capabilities",
                )
            )
        if update_fields:
            try:
                model.save(update_fields=update_fields)
            except IntegrityError as exc:
                if not is_unique_violation_error(exc):
                    raise
                raise AIProviderModelAlreadyConfigured(model.model_identifier) from exc
        clear_ai_provider_state_cache()
        return cls.get_model(model.id, workspace=model.provider_config.workspace)

    @staticmethod
    def delete_model(model: AIProviderModel) -> None:
        used_by = AIProviderHandler._feature_types_using_model(
            model, prune_orphans=True
        )
        if used_by:
            raise AIProviderModelInUse(model.model_identifier, sorted(used_by))
        model.delete()
        clear_ai_provider_state_cache()

    @staticmethod
    def _registered_default_model_feature_types() -> set[str]:
        """
        Return feature types whose default-model selection is currently active.

        :return: Registered feature identifiers supporting a default model.
        """

        return set(
            ai_provider_model_feature_type_registry.get_default_model_feature_types()
        )

    @staticmethod
    def _prune_orphaned_feature_settings(
        settings: list[AIProviderFeatureSetting],
        registered_feature_types: set[str],
    ) -> list[AIProviderFeatureSetting]:
        """
        Delete selections for unloaded features and return active selections.

        :param settings: Feature-setting rows considered by a mutation.
        :param registered_feature_types: Feature identifiers active in this process.
        :return: Settings belonging to currently registered features.
        """

        active_settings = [
            setting
            for setting in settings
            if setting.feature_type in registered_feature_types
        ]
        orphan_ids = [
            setting.id
            for setting in settings
            if setting.feature_type not in registered_feature_types
        ]
        if orphan_ids:
            AIProviderFeatureSetting.objects.filter(id__in=orphan_ids).delete()
        return active_settings

    @staticmethod
    def _feature_types_using_model(
        model: AIProviderModel,
        prune_orphans: bool = False,
    ) -> set[str]:
        """
        Return enabled registered features selecting a model.

        Explicit model deletion also removes unloaded-feature selections whose
        restricted foreign key would block deletion forever.

        :param model: The provider model whose selections are queried.
        :param prune_orphans: Whether an explicit delete may remove settings
            belonging to unloaded features.
        :return: Feature identifiers currently selecting the model.
        """

        registered_feature_types = (
            AIProviderHandler._registered_default_model_feature_types()
        )
        queryset = AIProviderFeatureSetting.objects.filter(model=model, is_enabled=True)
        if prune_orphans:
            active_settings = AIProviderHandler._prune_orphaned_feature_settings(
                list(queryset), registered_feature_types
            )
            return {setting.feature_type for setting in active_settings}
        return set(
            queryset.filter(feature_type__in=registered_feature_types).values_list(
                "feature_type", flat=True
            )
        )

    @classmethod
    def _ensure_provider_not_in_use(
        cls,
        provider: AIProviderConfig,
        workspace: Workspace | None = None,
        prune_orphans: bool = False,
    ) -> None:
        """
        Prevent availability changes while a scope resolves through the provider.

        :param provider: The provider whose usage is checked.
        :param workspace: An optional workspace restricting inherited-provider usage.
        :param prune_orphans: Whether an explicit delete may remove unloaded-feature
            settings whose restricted model relation blocks provider deletion.
        :raises AIProviderModelInUse: If an enabled feature resolves through the
            provider.
        """

        used_settings = AIProviderFeatureSetting.objects.filter(
            model__provider_config=provider,
            is_enabled=True,
        )
        if workspace is not None and provider.workspace_id is None:
            used_settings = used_settings.filter(
                Q(workspace=workspace) | Q(workspace__isnull=True)
            )
        registered_feature_types = cls._registered_default_model_feature_types()
        settings = list(used_settings.select_related("model").order_by("id"))
        if prune_orphans:
            settings = cls._prune_orphaned_feature_settings(
                settings, registered_feature_types
            )
        provider_settings = [
            setting
            for setting in settings
            if setting.feature_type in registered_feature_types
        ]
        if workspace is not None and provider.workspace_id is None:
            used_models = {
                resolution["feature_type"]: resolution["model"]
                for resolution in cls.list_feature_settings(workspace)
                if resolution["model"] is not None
                and resolution["model"].provider_config_id == provider.id
            }
        else:
            used_models = {
                setting.feature_type: setting.model for setting in provider_settings
            }
        if used_models:
            model = used_models[sorted(used_models)[0]]
            raise AIProviderModelInUse(
                model.model_identifier,
                sorted(
                    feature_type
                    for feature_type, used in used_models.items()
                    if used.id == model.id
                ),
            )

    @staticmethod
    def _is_feature_model_available(
        model: AIProviderModel | None,
        feature_type: str,
        state: ScopedAIProviderState,
    ) -> bool:
        """
        Check whether a feature can resolve through a model in one scope.

        :param model: The selected model, or None when nothing is selected.
        :param feature_type: The feature the model must be eligible for.
        :param state: The already-loaded provider state of the scope.
        :return: Whether the model is enabled, eligible and reachable in the scope.
        """

        if model is None or not model.is_enabled:
            return False
        if feature_type not in model.feature_types:
            return False

        provider = model.provider_config
        if not provider.is_active:
            return False
        if state.workspace is None:
            return provider.workspace_id is None
        if provider.workspace_id == state.workspace_id:
            return True
        if provider.workspace_id is not None:
            return False
        return provider.id not in state.disabled_instance_provider_ids

    @classmethod
    def list_feature_settings(
        cls,
        workspace: Workspace | None = None,
        state: ScopedAIProviderState | None = None,
    ) -> list[dict[str, Any]]:
        """
        Resolve the effective default-model setting of every feature in a scope.

        :param workspace: The workspace scope, or None for the instance scope.
        :param state: An already-loaded state for the scope, avoiding a reload.
        :return: One entry per default-model feature, holding its ``feature_type``,
            selection ``mode``, effective ``model``, resolved ``state`` and the
            instance-level ``inherited_model``/``inherited_state`` it falls back to.
        """

        if state is None:
            state = get_ai_provider_state(workspace)
        workspace = state.workspace

        result = []
        for (
            feature_type
        ) in ai_provider_model_feature_type_registry.get_default_model_feature_types():
            instance_setting = state.get_instance_feature_setting(feature_type)
            instance_model = None
            if instance_setting is None:
                instance_state = "unconfigured"
            elif not instance_setting.is_enabled:
                instance_state = "disabled"
            elif instance_setting.is_enabled:
                if cls._is_feature_model_available(
                    instance_setting.model, feature_type, state
                ):
                    instance_model = instance_setting.model
                    instance_state = "configured"
                else:
                    instance_state = "invalid"

            scoped_setting = (
                state.get_feature_setting(feature_type)
                if workspace is not None
                else instance_setting
            )
            if workspace is not None and scoped_setting is None:
                mode = AI_PROVIDER_FEATURE_MODE_INHERIT
                model = instance_model
                feature_state = "inherited" if model is not None else instance_state
            elif scoped_setting is None:
                mode = AI_PROVIDER_FEATURE_MODE_LEGACY
                model = None
                feature_state = "unconfigured"
            elif not scoped_setting.is_enabled:
                mode = AI_PROVIDER_FEATURE_MODE_DISABLED
                model = None
                feature_state = "disabled"
            else:
                mode = AI_PROVIDER_FEATURE_MODE_MODEL
                model = (
                    scoped_setting.model
                    if cls._is_feature_model_available(
                        scoped_setting.model, feature_type, state
                    )
                    else None
                )
                if model is None:
                    feature_state = "invalid"
                else:
                    feature_state = (
                        "overridden" if workspace is not None else "configured"
                    )

            result.append(
                {
                    "feature_type": feature_type,
                    "mode": mode,
                    "state": feature_state,
                    "model": model,
                    "inherited_model": instance_model
                    if workspace is not None
                    else None,
                    # Resolved against this workspace, so "invalid" means the instance
                    # selection exists but cannot be used here.
                    "inherited_state": instance_state
                    if workspace is not None
                    else None,
                }
            )
        return result

    @staticmethod
    def _reload_model(model: AIProviderModel) -> AIProviderModel:
        """
        Reload a selected model so stale references raise domain errors.

        :param model: The candidate model referenced by the caller.
        :return: The freshly loaded model with its provider relation.
        :raises AIProviderDoesNotExist: If the provider no longer exists.
        :raises AIProviderModelDoesNotExist: If the model no longer exists.
        """

        try:
            provider = AIProviderConfig.objects.get(id=model.provider_config_id)
        except AIProviderConfig.DoesNotExist as exc:
            raise AIProviderDoesNotExist(model.provider_config_id) from exc
        try:
            reloaded_model = AIProviderModel.objects.get(
                id=model.id, provider_config_id=provider.id
            )
        except AIProviderModel.DoesNotExist as exc:
            raise AIProviderModelDoesNotExist(model.id) from exc
        reloaded_model.provider_config = provider
        return reloaded_model

    @classmethod
    def update_feature_setting(
        cls,
        feature_type: str,
        mode: str,
        workspace: Workspace | None = None,
        model: AIProviderModel | None = None,
    ) -> dict[str, Any]:
        """
        Persist one scoped default-model feature mode.

        :param feature_type: The feature whose default-model mode is updated.
        :param mode: The requested selection mode.
        :param workspace: The workspace scope, or None for the instance scope.
        :param model: The selected model when using model mode.
        :return: The updated effective feature setting.
        :raises AIProviderFeatureModeNotAllowed: If the feature or scope does not
            support the requested mode.
        :raises AIProviderFeatureModelNotAvailable: If the selected or inherited
            model is unavailable in the scope.
        """

        feature = ai_provider_model_feature_type_registry.get(feature_type)
        if not feature.supports_default_model:
            raise AIProviderFeatureModeNotAllowed(feature_type)

        if mode == AI_PROVIDER_FEATURE_MODE_MODEL and model is not None:
            model = cls._reload_model(model)

        if mode == AI_PROVIDER_FEATURE_MODE_INHERIT:
            if workspace is None:
                raise AIProviderFeatureModeNotAllowed(mode)
            state = get_ai_provider_state(workspace)
            instance_setting = state.get_instance_feature_setting(feature_type)
            if (
                instance_setting is not None
                and instance_setting.is_enabled
                and not cls._is_feature_model_available(
                    instance_setting.model, feature_type, state
                )
            ):
                raise AIProviderFeatureModelNotAvailable(
                    feature_type,
                    getattr(instance_setting.model, "id", None),
                )
            AIProviderFeatureSetting.objects.filter(
                feature_type=feature_type, workspace=workspace
            ).delete()
        elif mode == AI_PROVIDER_FEATURE_MODE_LEGACY:
            if workspace is not None:
                raise AIProviderFeatureModeNotAllowed(mode)
            AIProviderFeatureSetting.objects.filter(
                feature_type=feature_type, workspace__isnull=True
            ).delete()
        elif mode == AI_PROVIDER_FEATURE_MODE_DISABLED:
            AIProviderFeatureSetting.objects.update_or_create(
                feature_type=feature_type,
                workspace=workspace,
                defaults={"is_enabled": False, "model": None},
            )
        elif mode == AI_PROVIDER_FEATURE_MODE_MODEL:
            if not cls._is_feature_model_available(
                model, feature_type, get_ai_provider_state(workspace)
            ):
                raise AIProviderFeatureModelNotAvailable(
                    feature_type, getattr(model, "id", None)
                )
            AIProviderFeatureSetting.objects.update_or_create(
                feature_type=feature_type,
                workspace=workspace,
                defaults={"is_enabled": True, "model": model},
            )
        else:
            raise AIProviderFeatureModeNotAllowed(mode)

        clear_ai_provider_state_cache()
        return next(
            setting
            for setting in cls.list_feature_settings(workspace)
            if setting["feature_type"] == feature_type
        )

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
        feature_types: list[str],
    ) -> dict[str, Any]:
        model_type = get_supported_provider_type(provider_type)
        required_capabilities = (
            ai_provider_model_feature_type_registry.get_required_model_capabilities(
                feature_types
            )
        )
        if AI_PROVIDER_MODEL_CAPABILITY_TOOLS in required_capabilities:
            capability_results = cls._test_text_and_tools(
                model_type,
                model_identifier,
                settings_override,
                secret_values,
            )
        else:
            capability_results = {
                AI_PROVIDER_MODEL_CAPABILITY_TEXT: cls._test_text(
                    model_type,
                    model_identifier,
                    settings_override,
                    secret_values,
                )
            }

        failed = [
            capability_results[capability]
            for capability in required_capabilities
            if capability_results[capability]["status"]
            == AI_PROVIDER_TEST_STATUS_FAILURE
        ]
        status = (
            AI_PROVIDER_TEST_STATUS_FAILURE
            if failed
            else AI_PROVIDER_TEST_STATUS_SUCCESS
        )
        error = next((result["error"] for result in failed if result["error"]), "")

        return {
            "model_id": model_id,
            "status": status,
            "error": error,
            "tested_at": timezone.now(),
            "capability_results": capability_results,
            "feature_results": (
                ai_provider_model_feature_type_registry.get_feature_test_results(
                    feature_types, capability_results
                )
            ),
        }

    @classmethod
    def _test_text(
        cls,
        model_type,
        model_identifier: str,
        settings_override: dict[str, Any],
        secret_values: list[str],
    ) -> dict[str, str]:
        try:
            response = model_type.prompt(
                model_identifier,
                "OK",
                settings_override=settings_override,
                model_settings_override={
                    "max_tokens": AI_PROVIDER_TEST_MAX_TOKENS,
                    "timeout": AI_PROVIDER_TEST_TIMEOUT_SECONDS,
                },
            )
            if not isinstance(response, str) or not response.strip():
                raise ModelTextResponseNotSupportedError(
                    "The model did not return a text response."
                )
        except Exception as exc:
            return {
                "status": AI_PROVIDER_TEST_STATUS_FAILURE,
                "error": cls.sanitize_test_error(exc, secret_values),
            }
        return {"status": AI_PROVIDER_TEST_STATUS_SUCCESS, "error": ""}

    @classmethod
    def _test_text_and_tools(
        cls,
        model_type,
        model_identifier: str,
        settings_override: dict[str, Any],
        secret_values: list[str],
    ) -> dict[str, dict[str, str]]:
        try:
            model = model_type.get_ai_model(
                model_identifier, settings_override=settings_override
            )
            test_model_text_and_tool_calling(
                model, max_tokens=AI_PROVIDER_TEST_MAX_TOKENS
            )
        except ModelToolCallingNotSupportedError as exc:
            text_result = (
                {"status": AI_PROVIDER_TEST_STATUS_SUCCESS, "error": ""}
                if exc.text_response_received
                else cls._test_text(
                    model_type,
                    model_identifier,
                    settings_override,
                    secret_values,
                )
            )
            return {
                AI_PROVIDER_MODEL_CAPABILITY_TEXT: text_result,
                AI_PROVIDER_MODEL_CAPABILITY_TOOLS: {
                    "status": AI_PROVIDER_TEST_STATUS_FAILURE,
                    "error": cls.sanitize_test_error(exc, secret_values),
                },
            }
        except ModelTextResponseNotSupportedError as exc:
            return {
                AI_PROVIDER_MODEL_CAPABILITY_TEXT: {
                    "status": AI_PROVIDER_TEST_STATUS_FAILURE,
                    "error": cls.sanitize_test_error(exc, secret_values),
                },
                AI_PROVIDER_MODEL_CAPABILITY_TOOLS: {
                    "status": (
                        AI_PROVIDER_TEST_STATUS_SUCCESS
                        if exc.tool_called
                        else AI_PROVIDER_TEST_STATUS_FAILURE
                    ),
                    "error": (
                        ""
                        if exc.tool_called
                        else cls.sanitize_test_error(exc, secret_values)
                    ),
                },
            }
        except Exception as exc:
            error = cls.sanitize_test_error(exc, secret_values)
            failed = {"status": AI_PROVIDER_TEST_STATUS_FAILURE, "error": error}
            return {
                AI_PROVIDER_MODEL_CAPABILITY_TEXT: failed,
                AI_PROVIDER_MODEL_CAPABILITY_TOOLS: failed,
            }
        passed = {"status": AI_PROVIDER_TEST_STATUS_SUCCESS, "error": ""}
        return {
            AI_PROVIDER_MODEL_CAPABILITY_TEXT: passed,
            AI_PROVIDER_MODEL_CAPABILITY_TOOLS: passed,
        }

    @classmethod
    def test_models(cls, models: list[AIProviderModel]) -> list[dict[str, Any]]:
        results = []
        for model in models:
            provider = model.provider_config
            settings_override = {
                name: provider.extra_settings.get(name)
                for name in AI_PROVIDER_TYPES[provider.provider_type]["extra_settings"]
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
                cls.secret_values(provider.api_key, provider.extra_settings),
                model.id,
                model.feature_types,
            )
            model.last_test_at = result["tested_at"]
            model.last_test_status = result["status"]
            model.last_test_error = result["error"]
            model.last_test_capabilities = result["capability_results"]
            model.save(
                update_fields=(
                    "last_test_at",
                    "last_test_status",
                    "last_test_error",
                    "last_test_capabilities",
                )
            )
            results.append(result)
        clear_ai_provider_state_cache()
        return results

    @staticmethod
    def secret_values(api_key: str, extra_settings: dict[str, Any]) -> list[str]:
        return [api_key] + [
            value for value in extra_settings.values() if isinstance(value, str)
        ]

    @staticmethod
    def sanitize_test_error(exc: Exception, secret_values: list[str]) -> str:
        message = get_user_friendly_error_message(exc)
        # Replace longer overlapping secrets first. Otherwise replacing a short
        # secret can leave the remainder of a longer secret visible.
        for value in sorted(
            {value for value in secret_values if value}, key=len, reverse=True
        ):
            message = message.replace(value, "[redacted]")
        return message[:1000]
