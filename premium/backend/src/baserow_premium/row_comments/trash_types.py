from typing import Any, Dict, Optional

from django.contrib.auth.models import AbstractUser

from baserow_premium.row_comments.models import RowComment
from baserow_premium.row_comments.operations import RestoreRowCommentOperationType
from baserow_premium.row_comments.signals import row_comment_restored

from baserow.contrib.database.table.models import Table
from baserow.core.exceptions import TrashItemDoesNotExist
from baserow.core.trash.registries import TrashableItemType


class RowCommentTrashableItemType(TrashableItemType):
    type = "row_comment"
    model_class = RowComment

    @property
    def requires_parent_id(self) -> bool:
        return False

    def trash(self, item_to_trash: RowComment, requesting_user, trash_entry):
        # Since we're using `updated_on` to determine if a comment has been
        # edited, we need to ensure that the comment is not considered edited
        # when it is trashed/restored.

        item_to_trash.trashed = True
        item_to_trash.save(update_fields=["trashed"])

    def permanently_delete_item(
        self,
        trashed_item: RowComment,
        trash_item_lookup_cache: Optional[Dict[str, RowComment]] = None,
    ):
        trashed_item.delete()

    def get_parent(self, trashed_item: RowComment) -> Optional[Any]:
        try:
            # If the table has been deleted already get_model will raise a
            # Table.DoesNotExist
            model = trashed_item.table.get_model()
            parent_row = model.objects_and_trash.get(id=trashed_item.row_id)
            return parent_row
        except (model.DoesNotExist, Table.DoesNotExist):
            # The parent row must have been actually deleted, in which case the
            # comment itself no longer exits.
            raise TrashItemDoesNotExist()

    def restore(self, trashed_item: RowComment, trash_entry):
        trashed_item.trashed = False
        trashed_item.save(update_fields=["trashed"])

        row_comment_restored.send(
            self,
            row_comment=trashed_item,
            user=trash_entry.user_who_trashed,
        )

    def get_owner(self, trashed_item: RowComment) -> Optional[AbstractUser]:
        return trashed_item.user

    def get_name(self, trashed_item: RowComment) -> str:
        return " "

    def get_restore_operation_type(self) -> str:
        return RestoreRowCommentOperationType.type

    def get_restore_operation_context(self, trashed_entry, trashed_item) -> str:
        return trashed_item.table
