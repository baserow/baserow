import dataclasses
from typing import Optional

from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import (
    RootActionScopeType,
    WorkspaceActionScopeType,
)


def _resolve_workspace(provider):
    """Try to resolve the workspace from a provider's scope GFK."""

    from baserow.core.models import Application, Workspace

    if provider.scope_content_type is None:
        return None

    model_class = provider.scope_content_type.model_class()
    if model_class == Workspace:
        return Workspace.objects.filter(id=provider.scope_object_id).first()
    elif model_class == Application:
        app = (
            Application.objects.filter(id=provider.scope_object_id)
            .select_related("workspace")
            .first()
        )
        return app.workspace if app else None
    return None


def _action_scope(workspace=None) -> ActionScopeStr:
    if workspace:
        return WorkspaceActionScopeType.value(workspace_id=workspace.id)
    return RootActionScopeType.value()


class CreateAIProviderActionType(ActionType):
    type = "create_ai_provider"
    description = ActionTypeDescription(
        _("Create AI provider"),
        _(
            'AI provider "%(provider_name)s" (%(provider_id)s) created '
            "at %(scope_type)s scope."
        ),
    )
    analytics_params = ["provider_id", "provider_type", "scope_type"]

    @dataclasses.dataclass
    class Params:
        provider_id: int
        provider_name: str
        provider_type: str
        scope_type: str
        scope_id: Optional[int]

    @classmethod
    def do(cls, user, provider, scope_type, scope_id=None):
        workspace = _resolve_workspace(provider)
        cls.register_action(
            user=user,
            params=cls.Params(
                provider_id=provider.id,
                provider_name=provider.name,
                provider_type=provider.provider_type,
                scope_type=scope_type,
                scope_id=scope_id,
            ),
            scope=cls.scope(workspace),
            workspace=workspace,
        )

    @classmethod
    def scope(cls, workspace=None) -> ActionScopeStr:
        return _action_scope(workspace)


class UpdateAIProviderActionType(ActionType):
    type = "update_ai_provider"
    description = ActionTypeDescription(
        _("Update AI provider"),
        _('AI provider "%(provider_name)s" (%(provider_id)s) updated.'),
    )
    analytics_params = ["provider_id"]

    @dataclasses.dataclass
    class Params:
        provider_id: int
        provider_name: str

    @classmethod
    def do(cls, user, provider):
        workspace = _resolve_workspace(provider)
        cls.register_action(
            user=user,
            params=cls.Params(
                provider_id=provider.id,
                provider_name=provider.name,
            ),
            scope=cls.scope(workspace),
            workspace=workspace,
        )

    @classmethod
    def scope(cls, workspace=None) -> ActionScopeStr:
        return _action_scope(workspace)


class DeleteAIProviderActionType(ActionType):
    type = "delete_ai_provider"
    description = ActionTypeDescription(
        _("Delete AI provider"),
        _('AI provider "%(provider_name)s" (%(provider_id)s) deleted.'),
    )
    analytics_params = ["provider_id"]

    @dataclasses.dataclass
    class Params:
        provider_id: int
        provider_name: str

    @classmethod
    def do(cls, user, provider_id, provider_name, workspace=None):
        cls.register_action(
            user=user,
            params=cls.Params(
                provider_id=provider_id,
                provider_name=provider_name,
            ),
            scope=cls.scope(workspace),
            workspace=workspace,
        )

    @classmethod
    def scope(cls, workspace=None) -> ActionScopeStr:
        return _action_scope(workspace)


class ToggleAIProviderOverrideActionType(ActionType):
    type = "toggle_ai_provider_override"
    description = ActionTypeDescription(
        _("Toggle AI provider override"),
        _(
            'AI provider "%(provider_name)s" (%(provider_id)s) '
            "%(action)s at %(scope_type)s scope."
        ),
    )
    analytics_params = ["provider_id", "is_enabled"]

    @dataclasses.dataclass
    class Params:
        provider_id: int
        provider_name: str
        scope_type: str
        is_enabled: bool
        action: str

    @classmethod
    def do(cls, user, provider, scope_type, is_enabled, workspace=None):
        cls.register_action(
            user=user,
            params=cls.Params(
                provider_id=provider.id,
                provider_name=provider.name,
                scope_type=scope_type,
                is_enabled=is_enabled,
                action="enabled" if is_enabled else "disabled",
            ),
            scope=cls.scope(workspace),
            workspace=workspace,
        )

    @classmethod
    def scope(cls, workspace=None) -> ActionScopeStr:
        return _action_scope(workspace)


class SetAIFeatureDefaultModelActionType(ActionType):
    type = "set_ai_feature_default_model"
    description = ActionTypeDescription(
        _("Set AI feature default model"),
        _(
            'Default model for "%(feature_type)s" set to '
            '"%(model_identifier)s" at %(scope_type)s scope.'
        ),
    )
    analytics_params = ["feature_type", "model_identifier"]

    @dataclasses.dataclass
    class Params:
        feature_type: str
        model_identifier: str
        provider_name: str
        scope_type: str

    @classmethod
    def do(cls, user, feature_type, provider_model, scope_type, workspace=None):
        cls.register_action(
            user=user,
            params=cls.Params(
                feature_type=feature_type,
                model_identifier=provider_model.model_identifier,
                provider_name=provider_model.provider_config.name,
                scope_type=scope_type,
            ),
            scope=cls.scope(workspace),
            workspace=workspace,
        )

    @classmethod
    def scope(cls, workspace=None) -> ActionScopeStr:
        return _action_scope(workspace)
