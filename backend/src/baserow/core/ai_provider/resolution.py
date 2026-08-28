from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from django.db.models import Q

from baserow.core.cache import local_cache
from baserow.core.feature_flags import FF_AI_PROVIDERS, feature_flag_is_enabled
from baserow.core.models import Workspace

from .models import (
    AIProviderConfig,
    AIProviderFeatureSetting,
    AIProviderWorkspaceOverride,
)

AI_PROVIDER_STATE_LOCAL_CACHE_KEY = "ai_provider_state"


@dataclass(frozen=True, slots=True)
class ScopedAIProviderState:
    """
    Every AI provider row needed to resolve one scope, already in memory.

    A scope is either the instance (``workspace`` is ``None``) or one workspace.
    Resolution reads only from this object, so answering many questions about a
    scope costs the queries of a single load instead of one load per question.
    """

    workspace: Workspace | None = None
    owned_providers: dict[str, AIProviderConfig] = field(default_factory=dict)
    instance_providers: dict[str, AIProviderConfig] = field(default_factory=dict)
    disabled_instance_provider_ids: frozenset[int] = frozenset()
    feature_settings: dict[str, AIProviderFeatureSetting] = field(default_factory=dict)
    instance_feature_settings: dict[str, AIProviderFeatureSetting] = field(
        default_factory=dict
    )

    @property
    def workspace_id(self) -> int | None:
        return self.workspace.id if self.workspace is not None else None

    def get_feature_setting(self, feature_type: str) -> AIProviderFeatureSetting | None:
        """Return this scope's own setting, without falling back to the instance."""

        return self.feature_settings.get(feature_type)

    def get_instance_feature_setting(
        self, feature_type: str
    ) -> AIProviderFeatureSetting | None:
        return self.instance_feature_settings.get(feature_type)


def load_ai_provider_state(
    workspaces: Iterable[Workspace] = (),
) -> dict[int | None, ScopedAIProviderState]:
    """
    Load the instance scope and every given workspace scope in one go.

    The query count is fixed regardless of how many workspaces are requested,
    which is what keeps list serialization off an N+1.

    :param workspaces: The workspaces to load a scope for.
    :return: The state per scope, keyed by workspace id with ``None`` for the
        instance scope.
    """

    workspaces = [
        workspace for workspace in workspaces if isinstance(workspace, Workspace)
    ]
    workspace_ids = [workspace.id for workspace in workspaces]

    if not feature_flag_is_enabled(FF_AI_PROVIDERS):
        # Nothing resolves through these tables yet, so do not read them at all.
        return {
            None: ScopedAIProviderState(),
            **{
                workspace.id: ScopedAIProviderState(workspace=workspace)
                for workspace in workspaces
            },
        }

    scope = Q(workspace__isnull=True)
    if workspace_ids:
        scope |= Q(workspace_id__in=workspace_ids)

    instance_providers: dict[str, AIProviderConfig] = {}
    owned_providers: dict[int, dict[str, AIProviderConfig]] = {
        workspace_id: {} for workspace_id in workspace_ids
    }
    for provider in AIProviderConfig.objects.filter(scope).prefetch_related("models"):
        if provider.workspace_id is None:
            instance_providers[provider.provider_type] = provider
        else:
            owned_providers[provider.workspace_id][provider.provider_type] = provider

    disabled_provider_ids: dict[int, set[int]] = {
        workspace_id: set() for workspace_id in workspace_ids
    }
    if workspace_ids:
        overrides = AIProviderWorkspaceOverride.objects.filter(
            workspace_id__in=workspace_ids
        ).values_list("workspace_id", "provider_config_id")
        for workspace_id, provider_config_id in overrides:
            disabled_provider_ids[workspace_id].add(provider_config_id)

    settings_per_scope: dict[int | None, dict[str, AIProviderFeatureSetting]] = {
        None: {},
        **{workspace_id: {} for workspace_id in workspace_ids},
    }
    feature_settings = AIProviderFeatureSetting.objects.filter(scope).select_related(
        "model__provider_config"
    )
    for setting in feature_settings:
        settings_per_scope[setting.workspace_id][setting.feature_type] = setting

    instance_feature_settings = settings_per_scope[None]
    states: dict[int | None, ScopedAIProviderState] = {
        None: ScopedAIProviderState(
            instance_providers=instance_providers,
            feature_settings=instance_feature_settings,
            instance_feature_settings=instance_feature_settings,
        )
    }
    for workspace in workspaces:
        states[workspace.id] = ScopedAIProviderState(
            workspace=workspace,
            owned_providers=owned_providers[workspace.id],
            instance_providers=instance_providers,
            disabled_instance_provider_ids=frozenset(
                disabled_provider_ids[workspace.id]
            ),
            feature_settings=settings_per_scope[workspace.id],
            instance_feature_settings=instance_feature_settings,
        )
    return states


def get_ai_provider_state(
    workspace: Workspace | None = None,
) -> ScopedAIProviderState:
    """
    Load the state of a single scope, reusing the snapshot already loaded here.

    :param workspace: The workspace scope, or None for the instance scope.
    :return: The fully loaded provider state for the requested scope.
    """

    workspace = workspace if isinstance(workspace, Workspace) else None
    workspace_id = workspace.id if workspace is not None else None

    def load_scope() -> ScopedAIProviderState:
        workspaces = [workspace] if workspace is not None else []
        return load_ai_provider_state(workspaces)[workspace_id]

    return local_cache.get(
        f"{AI_PROVIDER_STATE_LOCAL_CACHE_KEY}:{workspace_id or 'instance'}",
        load_scope,
    )


def clear_ai_provider_state_cache() -> None:
    """
    Discard provider-state snapshots held by the current request or task.

    :return: None.
    """

    local_cache.delete(f"{AI_PROVIDER_STATE_LOCAL_CACHE_KEY}:*")
