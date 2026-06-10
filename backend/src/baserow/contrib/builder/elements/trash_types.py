from typing import TYPE_CHECKING, List

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.operations import RestoreElementOperationType
from baserow.core.graph.models import GraphPointTrashableItemType
from baserow.core.models import TrashEntry

from .signals import element_deleted, elements_created

if TYPE_CHECKING:
    from baserow.contrib.builder.pages.models import Page


class ElementTrashableItemType(GraphPointTrashableItemType):
    """
    Trashable item type for `Element`.

    The graph-aware trash/restore behaviour (removing the element from its page
    graph, cascading to its children and re-inserting everything on restore) is
    inherited from `GraphPointTrashableItemType`. This class only layers on
    the builder-specific concerns: emitting the element realtime signals and
    invalidating the page's element cache.
    """

    type = "builder_element"
    model_class = Element

    def get_parent(self, trashed_item: Element) -> "Page":
        return trashed_item.page

    def trash(
        self,
        item_to_trash: Element,
        requesting_user: AbstractUser,
        trash_entry: TrashEntry,
    ) -> None:
        """
        Trash the element via the base graph logic, then notify clients the element
        was deleted and invalidate the page's element cache.
        """

        # The base returns the full set of trashed records (the element plus any
        # cascaded descendants). Realtime receivers need the descendants separately
        # so other clients can remove a trashed container's whole subtree.
        trashed = super().trash(item_to_trash, requesting_user, trash_entry)
        descendant_ids = [
            record.id for record in trashed if record.id != item_to_trash.id
        ]

        element_deleted.send(
            self,
            element_id=item_to_trash.id,
            page=item_to_trash.page,
            user=requesting_user,
            descendant_ids=descendant_ids,
        )
        ElementHandler().invalidate_element_cache(item_to_trash.page)

    def restore(self, trashed_item: Element, trash_entry: TrashEntry) -> None:
        """
        Restore the element (and any cascaded children) via the base graph logic,
        then invalidate the page's element cache and broadcast the restored
        elements so clients re-create them.
        """

        restored_elements: List[Element] = super().restore(trashed_item, trash_entry)
        ElementHandler().invalidate_element_cache(trashed_item.page)
        elements_created.send(
            self,
            elements=restored_elements,
            page=trashed_item.page,
            user=None,
        )

    def _before_permanent_delete(self, item: Element) -> None:
        """
        Clean up the element's owned related data (e.g. a collection element's
        fields, a menu element's items) when it is permanently deleted. This runs
        only on permanent deletion — never at trash time — so that a restore brings
        the element back with its related data intact.
        """

        item.get_type().before_delete(item)

    def get_restore_operation_type(self) -> str:
        return RestoreElementOperationType.type
