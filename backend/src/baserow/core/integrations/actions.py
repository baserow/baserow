from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import ActionTypeDescription, UndoableActionType
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.service import IntegrationService
from baserow.core.integrations.trash_types import IntegrationTrashableItemType
from baserow.core.models import Application
from baserow.core.trash.handler import TrashHandler

INTEGRATION_ACTION_CONTEXT = _(
    'in application "%(application_name)s" (%(application_id)s).'
)


class CreateIntegrationActionType(UndoableActionType):
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
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )
        return integration

    @classmethod
    def scope(cls, application_id: int):
        return ApplicationActionScopeType.value(application_id)

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


class UpdateIntegrationActionType(UndoableActionType):
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

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        integration: Integration,
        **kwargs,
    ) -> Integration:
        updated = IntegrationService().update_integration(user, integration, **kwargs)

        application = updated.integration.application
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                updated.integration.id,
                updated.original_values,
                updated.new_values,
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )
        return updated.integration

    @classmethod
    def scope(cls, application_id: int):
        return ApplicationActionScopeType.value(application_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        integration = IntegrationHandler().get_integration_for_update(
            params.integration_id
        )
        IntegrationService().update_integration(
            user, integration, **params.integration_original_params
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        integration = IntegrationHandler().get_integration_for_update(
            params.integration_id
        )
        IntegrationService().update_integration(
            user, integration, **params.integration_new_params
        )


class DeleteIntegrationActionType(UndoableActionType):
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

    @classmethod
    def do(cls, user: AbstractUser, integration: Integration) -> None:
        application = integration.application
        # Captured before the integration is trashed.
        params = cls.Params(
            application.id,
            application.name,
            integration.id,
        )

        IntegrationService().delete_integration(user, integration)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )

    @classmethod
    def scope(cls, application_id: int):
        return ApplicationActionScopeType.value(application_id)

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


class MoveIntegrationActionType(UndoableActionType):
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
            ),
            scope=cls.scope(application.id),
            workspace=application.workspace,
        )
        return moved_integration

    @classmethod
    def scope(cls, application_id: int):
        return ApplicationActionScopeType.value(application_id)

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
