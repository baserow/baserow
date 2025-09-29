from typing import Any, Optional

from baserow.core.models import Application, TrashEntry, Workspace
from baserow.core.operations import (
    RestoreApplicationOperationType,
    RestoreWorkspaceOperationType,
)
from baserow.core.registries import application_type_registry
from baserow.core.signals import application_created, workspace_restored
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.trash.registries import TrashableItemType, trash_item_type_registry


class ApplicationTrashableItemType(TrashableItemType):
    type = "application"
    model_class = Application

    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        return trashed_item.workspace

    def get_name(self, trashed_item: Application) -> str:
        return trashed_item.name

    def restore(
        self,
        trashed_item: Application,
        trash_entry: TrashEntry,
    ):
        super().restore(trashed_item, trash_entry)
        application_created.send(
            self,
            application=trashed_item,
            user=None,
        )

    def permanently_delete_item(
        self, trashed_item: Application, trash_item_lookup_cache=None
    ):
        """
        Deletes an application and the related relations in the correct way.
        """

        SnapshotHandler().delete_by_application(trashed_item)

        application = trashed_item.specific
        application_type = application_type_registry.get_by_model(application)
        application_type.pre_delete(application)
        application.delete()
        return application

    def get_restore_operation_type(self) -> str:
        return RestoreApplicationOperationType.type


class WorkspaceTrashableItemType(TrashableItemType):
    type = "workspace"
    model_class = Workspace

    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        return None

    def get_name(self, trashed_item: Workspace) -> str:
        return trashed_item.name

    def restore(self, trashed_item: Workspace, trash_entry: TrashEntry):
        """
        Informs any clients that the workspace exists again.
        """

        super().restore(trashed_item, trash_entry)
        for workspace_user in trashed_item.workspaceuser_set.all():
            workspace_restored.send(self, workspace_user=workspace_user, user=None)

    def permanently_delete_item(
        self, trashed_workspace: Workspace, trash_item_lookup_cache=None
    ):
        """
        Deletes the provided workspace and all of its applications permanently.
        """

        # Select all the applications so we can delete them via the handler which is
        # needed in order to call the pre_delete method for each application.
        applications = (
            trashed_workspace.application_set(manager="objects_and_trash")
            .all()
            .select_related("workspace")
        )
        application_trashable_type = trash_item_type_registry.get("application")
        for application in applications:
            application_trashable_type.permanently_delete_item(application)

        trashed_workspace.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreWorkspaceOperationType.type
