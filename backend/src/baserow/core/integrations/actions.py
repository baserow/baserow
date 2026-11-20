from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
    render_action_type_description,
)
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    ApplicationActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.integrations.exceptions import IntegrationUsedSincePromotion
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.service import IntegrationService
from baserow.core.integrations.trash_types import IntegrationTrashableItemType
from baserow.core.models import Application
from baserow.core.services.models import Service
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_sources.models import UserSource

INTEGRATION_ACTION_CONTEXT = _(
    'in application "%(application_name)s" (%(application_id)s).'
)


class IntegrationActionTypeMixin:
    """
    A workspace integration is managed from the workspace settings and used from
    every application of the workspace, so its actions are undone from anywhere in
    the workspace and described in it, never in the hidden shared application that
    owns it. They record the workspace in `workspace_id` and `workspace_name`, which
    stay `None` for the integration of an application.
    """

    @classmethod
    def scope(cls, application: Application) -> ActionScopeStr:
        if IntegrationHandler().is_shared_application(application):
            return WorkspaceActionScopeType.value(application.workspace_id)
        return ApplicationActionScopeType.value(application.id)

    @classmethod
    def get_workspace_params(cls, application: Application) -> Dict[str, Any]:
        """
        :param application: The application that holds the integration.
        :return: The workspace params of the action, empty for the integration of
            an application.
        """

        if not IntegrationHandler().is_shared_application(application):
            return {}
        return {
            "workspace_id": application.workspace_id,
            "workspace_name": application.workspace.name,
        }

    @classmethod
    def get_long_description(cls, params_dict: Dict[str, Any], *args, **kwargs) -> str:
        if params_dict.get("workspace_id") is None:
            return super().get_long_description(params_dict, *args, **kwargs)

        description = ActionTypeDescription(
            cls.description.short, cls.description.long, WORKSPACE_ACTION_CONTEXT
        )
        return render_action_type_description(description, params_dict)


class CreateIntegrationActionType(IntegrationActionTypeMixin, UndoableActionType):
    type = "create_integration"
    description = ActionTypeDescription(
        _("Create integration"),
        _("Integration (%(integration_id)s) created"),
        INTEGRATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        integration_id: int
        integration_type: str
        workspace_id: Optional[int] = None
        workspace_name: Optional[str] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        integration_type: IntegrationType,
        application: Application,
        before: Optional[Integration] = None,
        **kwargs,
    ) -> Integration:
        integration = IntegrationService().create_integration(
            user, integration_type, application, before=before, **kwargs
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                integration.id,
                integration_type.type,
                **cls.get_workspace_params(application),
            ),
            scope=cls.scope(application),
            workspace=application.workspace,
        )
        return integration

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        integration = IntegrationHandler().get_integration_for_update(
            params.integration_id
        )
        IntegrationService().delete_integration(user, integration)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(
            user,
            IntegrationTrashableItemType.type,
            params.integration_id,
        )


class UpdateIntegrationActionType(IntegrationActionTypeMixin, UndoableActionType):
    """
    Undo and redo replay the logged values without any credential. The fields
    in `IntegrationType.get_action_log_excluded_fields`, which include every
    target a credential protects, are never logged, so a replay cannot re-point
    a stored password. If a replay does trip `IntegrationCredentialRequired`,
    the action handler rolls it back and records the error on the action.

    An update that promotes the integration also records the services and user
    sources using it. Undoing moves it back to its application, where any that
    started using it since, maybe from other applications, couldn't use it any
    more, so the undo fails then and the integration stays in the workspace.
    """

    type = "update_integration"
    description = ActionTypeDescription(
        _("Update integration"),
        _("Integration (%(integration_id)s) updated"),
        INTEGRATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        integration_id: int
        integration_original_params: Dict[str, Any]
        integration_new_params: Dict[str, Any]
        workspace_id: Optional[int] = None
        workspace_name: Optional[str] = None
        # Set when the update moved the integration to another application.
        service_ids: Optional[List[int]] = None
        user_source_ids: Optional[List[int]] = None

    @classmethod
    def _get_using_ids(cls, integration_id: int) -> Tuple[List[int], List[int]]:
        """
        :param integration_id: The ID of the integration.
        :return: The IDs of the services and of the user sources using it,
            trashed ones included, as they use it again once restored.
        """

        services = Service.objects_and_trash.filter(integration=integration_id)
        user_sources = UserSource.objects_and_trash.filter(integration=integration_id)
        return (
            list(services.values_list("id", flat=True)),
            list(user_sources.values_list("id", flat=True)),
        )

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        integration: Integration,
        **kwargs,
    ) -> Integration:
        updated = IntegrationService().update_integration(user, integration, **kwargs)

        service_ids, user_source_ids = None, None
        if "application_id" in updated.new_values:
            service_ids, user_source_ids = cls._get_using_ids(updated.integration.id)

        application = updated.integration.application
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                updated.integration.id,
                updated.original_values,
                updated.new_values,
                **cls.get_workspace_params(application),
                service_ids=service_ids,
                user_source_ids=user_source_ids,
            ),
            scope=cls.scope(application),
            workspace=application.workspace,
        )
        return updated.integration

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        integration = IntegrationHandler().get_integration_for_update(
            params.integration_id
        )

        promoted = params.service_ids is not None
        if promoted:
            service_ids, user_source_ids = cls._get_using_ids(integration.id)
            new_service_ids = set(service_ids) - set(params.service_ids)
            new_user_source_ids = set(user_source_ids) - set(params.user_source_ids)
            if new_service_ids or new_user_source_ids:
                raise IntegrationUsedSincePromotion()

        IntegrationService().update_integration(
            user,
            integration,
            # Nothing else may move it out of the workspace, as only the check
            # above makes sure no other application uses it by now.
            allow_demotion=promoted,
            **params.integration_original_params,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        integration = IntegrationHandler().get_integration_for_update(
            params.integration_id
        )
        IntegrationService().update_integration(
            user, integration, **params.integration_new_params
        )


class DeleteIntegrationActionType(IntegrationActionTypeMixin, UndoableActionType):
    type = "delete_integration"
    description = ActionTypeDescription(
        _("Delete integration"),
        _("Integration (%(integration_id)s) deleted"),
        INTEGRATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        integration_id: int
        workspace_id: Optional[int] = None
        workspace_name: Optional[str] = None

    @classmethod
    def do(cls, user: AbstractUser, integration: Integration) -> None:
        application = integration.application
        # Captured before the integration is trashed.
        params = cls.Params(
            application.id,
            application.name,
            integration.id,
            **cls.get_workspace_params(application),
        )

        IntegrationService().delete_integration(user, integration)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(application),
            workspace=application.workspace,
        )

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        TrashHandler.restore_item(
            user,
            IntegrationTrashableItemType.type,
            params.integration_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        integration = IntegrationHandler().get_integration_for_update(
            params.integration_id
        )
        IntegrationService().delete_integration(user, integration)


class MoveIntegrationActionType(IntegrationActionTypeMixin, UndoableActionType):
    type = "move_integration"
    description = ActionTypeDescription(
        _("Move integration"),
        _("Integration (%(integration_id)s) moved"),
        INTEGRATION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        application_id: int
        application_name: str
        integration_id: int
        original_before_id: Optional[int]
        new_before_id: Optional[int]
        workspace_id: Optional[int] = None
        workspace_name: Optional[str] = None

    @classmethod
    def _ordered_sibling_ids(cls, integration: Integration) -> List[int]:
        return list(
            Integration.objects.filter(application_id=integration.application_id)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        integration: Integration,
        before: Optional[Integration] = None,
    ) -> Integration:
        application = integration.application

        # Capture the sibling that originally came right after the integration so the
        # move can be undone by placing it back before that sibling.
        sibling_ids = cls._ordered_sibling_ids(integration)
        index = sibling_ids.index(integration.id)
        original_before_id = (
            sibling_ids[index + 1] if index + 1 < len(sibling_ids) else None
        )

        moved_integration = IntegrationService().move_integration(
            user, integration, before
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                integration.id,
                original_before_id,
                before.id if before else None,
                **cls.get_workspace_params(application),
            ),
            scope=cls.scope(application),
            workspace=application.workspace,
        )
        return moved_integration

    @classmethod
    def _move(cls, user: AbstractUser, integration_id: int, before_id: Optional[int]):
        integration = IntegrationHandler().get_integration_for_update(integration_id)
        before = IntegrationHandler().get_integration(before_id) if before_id else None
        IntegrationService().move_integration(user, integration, before)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._move(user, params.integration_id, params.original_before_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._move(user, params.integration_id, params.new_before_id)
