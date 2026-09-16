from typing import Any, Optional

from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.fields.operations import UpdateFieldOperationType
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.contrib.database.workflow_actions.signals import (
    workflow_action_created,
    workflow_action_deleted,
)
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType


class DatabaseWorkflowActionTrashableItemType(TrashableItemType):
    """
    A button field's action, trashed on its own so deleting one can be undone
    with its service intact. Trashing the field does not trash its actions: they
    stay with the field and come back with it (ADR 006 section 8).
    """

    type = "database_workflow_action"
    model_class = DatabaseWorkflowAction

    def get_parent(self, trashed_item: DatabaseWorkflowAction) -> ButtonField:
        return trashed_item.field

    def get_name(self, trashed_item: DatabaseWorkflowAction) -> str:
        # The position tells two actions of one type on the same button apart,
        # as the builder's name does with the element.
        return (
            f"{trashed_item.get_type().type} #{trashed_item.order} ({trashed_item.id})"
        )

    def trash(
        self,
        item_to_trash: DatabaseWorkflowAction,
        requesting_user,
        trash_entry: TrashEntry,
    ) -> None:
        super().trash(item_to_trash, requesting_user, trash_entry)
        workflow_action_deleted.send(
            self,
            workflow_action_id=item_to_trash.id,
            field=item_to_trash.field,
            user=requesting_user,
        )

    def restore(
        self, trashed_item: DatabaseWorkflowAction, trash_entry: TrashEntry
    ) -> None:
        super().restore(trashed_item, trash_entry)
        workflow_action_created.send(
            self, workflow_action=trashed_item.specific, user=None
        )

    def permanently_delete_item(
        self,
        trashed_item: DatabaseWorkflowAction,
        trash_item_lookup_cache: Optional[Any] = None,
    ) -> None:
        # The pre-delete receiver deletes the service, so it only goes once the
        # action can no longer be restored.
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        # Configuring a button's actions is configuring the field (ADR 006
        # section 5), and restoring one is no different.
        return UpdateFieldOperationType.type

    def get_restore_operation_context(
        self, trash_entry: TrashEntry, trashed_item: DatabaseWorkflowAction
    ) -> ButtonField:
        return trashed_item.field
