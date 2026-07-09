from typing import TYPE_CHECKING, Any, Optional

from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.builder.workflow_actions.operations import (
    RestoreBuilderWorkflowActionOperationType,
)
from baserow.contrib.builder.workflow_actions.signals import (
    workflow_action_created,
    workflow_action_deleted,
)
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

if TYPE_CHECKING:
    from baserow.contrib.builder.pages.models import Page


class BuilderWorkflowActionTrashableItemType(TrashableItemType):
    type = "builder_workflow_action"
    model_class = BuilderWorkflowAction

    def get_parent(self, trashed_item: BuilderWorkflowAction) -> "Page":
        return trashed_item.page

    def get_name(self, trashed_item: BuilderWorkflowAction) -> str:
        name = f"{trashed_item.get_type().type} ({trashed_item.id})"
        # Mention the parent element (if any) so that, when the workflow action is
        # shown in the trash, the user can tell which element it belongs to.
        element = trashed_item.element
        if element is not None:
            name += f" inside {element} ({element.id})"
        return name.lower()

    def trash(
        self,
        item_to_trash: BuilderWorkflowAction,
        requesting_user,
        trash_entry: TrashEntry,
    ) -> None:
        page = item_to_trash.page
        super().trash(item_to_trash, requesting_user, trash_entry)
        workflow_action_deleted.send(
            self,
            workflow_action_id=item_to_trash.id,
            page=page,
            user=requesting_user,
        )

    def restore(
        self, trashed_item: BuilderWorkflowAction, trash_entry: TrashEntry
    ) -> None:
        super().restore(trashed_item, trash_entry)
        workflow_action_created.send(
            self,
            workflow_action=trashed_item.specific,
            user=None,
            before_id=None,
        )

    def permanently_delete_item(
        self,
        trashed_item: BuilderWorkflowAction,
        trash_item_lookup_cache: Optional[Any] = None,
    ) -> None:
        # Hard-deleting the workflow action fires the pre-delete receiver
        # (`before_permanently_deleted`) which cleans up the underlying service (for
        # service-backed actions). This only runs on permanent deletion, so a restore
        # brings the action back with its service intact.
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreBuilderWorkflowActionOperationType.type
