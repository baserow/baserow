from typing import TYPE_CHECKING, Any, Optional

from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import (
    RestoreIntegrationOperationType,
    RestoreWorkspaceIntegrationOperationType,
)
from baserow.core.integrations.signals import (
    integration_created,
    integration_deleted,
)
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

if TYPE_CHECKING:
    from baserow.core.models import Application, Workspace


class IntegrationTrashableItemType(TrashableItemType):
    """
    A workspace integration is trashed under its workspace, never under the hidden
    shared application that owns it, and only those allowed to manage it can
    restore it.
    """

    type = "integration"
    model_class = Integration

    def get_parent(self, trashed_item: Integration) -> "Application | Workspace":
        application = trashed_item.application
        if IntegrationHandler().is_shared_application(application):
            return application.workspace
        return application

    def get_name(self, trashed_item: Integration) -> str:
        # The application or the workspace is already shown as the trash entry's
        # parent (get_parent returns it), so it isn't repeated here.
        return f"{trashed_item.name} ({trashed_item.id})"

    def trash(
        self,
        item_to_trash: Integration,
        requesting_user,
        trash_entry: TrashEntry,
    ) -> None:
        application = item_to_trash.application
        super().trash(item_to_trash, requesting_user, trash_entry)
        integration_deleted.send(
            self,
            integration_id=item_to_trash.id,
            application=application,
            user=requesting_user,
        )

    def restore(self, trashed_item: Integration, trash_entry: TrashEntry) -> None:
        super().restore(trashed_item, trash_entry)
        integration_created.send(
            self,
            integration=trashed_item,
            user=None,
            before_id=None,
        )

    def permanently_delete_item(
        self, trashed_item: Integration, trash_item_lookup_cache: Optional[Any] = None
    ) -> None:
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreIntegrationOperationType.type

    def get_restore_operation_types(self, trashed_item: Integration) -> list[str]:
        """
        A workspace integration is restored with the workspace operation, for the
        same reason it is deleted with one, see `IntegrationService`.

        :param trashed_item: The trashed integration.
        :return: The restore operation to check on the integration.
        """

        if IntegrationHandler().is_shared_application(trashed_item.application):
            return [RestoreWorkspaceIntegrationOperationType.type]
        return [self.get_restore_operation_type()]
