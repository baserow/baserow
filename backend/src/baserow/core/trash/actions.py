import dataclasses
from typing import Any, Dict, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionType,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    WorkspaceActionScopeType,
)
from baserow.core.exceptions import ApplicationDoesNotExist, WorkspaceDoesNotExist
from baserow.core.models import Application, Workspace
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.handler import TrashHandler
from baserow.core.trash.exceptions import CannotUndoRestoreError


class EmptyTrashActionType(ActionType):
    type = "empty_trash"
    description = ActionTypeDescription(
        _("Empty trash"),
        _(
            'Trash for application "%(application_name)s" (%(application_id)s) has been emptied'
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "application_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_id: Optional[int] = None
        application_name: Optional[str] = None

    @classmethod
    def _get_application(cls, application_id: int):
        try:
            return Application.objects_and_trash.get(id=application_id)
        except Application.DoesNotExist:
            raise ApplicationDoesNotExist

    @classmethod
    def _get_workspace(cls, workspace_id: int):
        try:
            return Workspace.objects_and_trash.get(id=workspace_id)
        except Workspace.DoesNotExist:
            raise WorkspaceDoesNotExist

    @classmethod
    def do(
        cls, user: AbstractUser, workspace_id: int, application_id: Optional[int] = None
    ):
        application_name = None
        workspace = None
        if application_id is not None:
            application = cls._get_application(application_id)
            application_name = application.name
            workspace = application.workspace
        else:
            workspace = cls._get_workspace(workspace_id)

        TrashHandler().empty(user, workspace_id, application_id)

        cls.register_action(
            user,
            cls.Params(workspace_id, workspace.name, application_id, application_name),
            cls.scope(workspace_id),
            workspace,
        )

    @classmethod
    def scope(cls, workspace_id: int):
        return WorkspaceActionScopeType.value(workspace_id)

    @classmethod
    def get_long_description(cls, params_dict: Dict[str, Any], *args, **kwargs) -> str:
        if params_dict.get("application_id") is None:
            return (
                _(
                    'Trash for workspace "%(workspace_name)s" (%(workspace_id)s) has been emptied.'
                )
                % params_dict
            )

        return super().get_long_description(params_dict, *args, **kwargs)


class RestoreFromTrashActionType(UndoableActionType):
    type = "restore_from_trash"
    description = ActionTypeDescription(
        _("Restore from trash"),
        _('Item of type "%(item_type)s" (%(item_id)s) has been restored from trash'),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "item_id",
    ]

    @dataclasses.dataclass
    class Params:
        item_id: int
        item_type: str
        workspace_id: int
        workspace_name: str
        parent_item_id: int | None = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        trash_item_type: str,
        trash_item_id: int,
        parent_trash_item_id: Optional[int] = None,
    ):
        trash_entry = TrashHandler.get_trash_entry(
            trash_item_type, trash_item_id, parent_trash_item_id
        )

        # Managed trashed entries cannot be manually restored.
        if trash_entry.managed:
            raise TrashItemRestorationDisallowed(
                "This trash entry is managed internally and cannot be restored manually."
            )

        workspace = trash_entry.workspace
        TrashHandler.restore_item(
            user, trash_item_type, trash_item_id, parent_trash_item_id
        )

        cls.register_action(
            user,
            cls.Params(
                trash_item_id,
                trash_item_type,
                workspace.id,
                workspace.name,
                parent_item_id=parent_trash_item_id,
            ),
            cls.scope(workspace.id),
            workspace,
        )

    @classmethod
    def scope(cls, workspace_id: int):
        return WorkspaceActionScopeType.value(workspace_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        """
        Undo the restore by trashing the item again.
        Raises CannotUndoRestoreError if the item cannot be returned to trash.
        """
        from baserow.core.trash.registries import trash_item_type_registry

        try:
            # Get the trashable item type
            trashable_item_type = trash_item_type_registry.get(params.item_type)

            # Look up the restored (non-trashed) item
            item = trashable_item_type.model_class.objects.get(id=params.item_id)

            # Get the workspace and application if needed
            workspace = Workspace.objects.get(id=params.workspace_id)
            application = getattr(item, "application", None)

            # Trash the item again
            TrashHandler.trash(user, workspace, application, item)
        except Exception as e:
            # Raise our specific error so the frontend can handle it properly
            raise CannotUndoRestoreError(
                f"Cannot undo restore operation for {params.item_type} (ID: {params.item_id}). "
                f"The item may have been modified or is no longer in the expected state."
            )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        """
        Redo the restore by restoring the item from trash again.
        """
        TrashHandler.restore_item(
            user,
            params.item_type,
            params.item_id,
            params.parent_item_id,
        )