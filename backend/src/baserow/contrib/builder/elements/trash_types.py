from typing import Any, List, Optional

from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.operations import RestoreElementOperationType
from baserow.core.models import TrashEntry
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.registries import TrashableItemType

from .signals import element_deleted, elements_created


class ElementTrashableItemType(TrashableItemType):
    type = "builder_element"
    model_class = Element

    def get_parent(self, trashed_item: Element) -> Optional[Any]:
        return trashed_item.page

    def get_name(self, trashed_item: Element) -> str:
        return f"{trashed_item} ({trashed_item.id})".lower()

    def get_additional_restoration_data(self, trashed_item: Element):
        graph = trashed_item.page.get_graph()
        position_triplet = graph.get_position(trashed_item)

        # Capture all descendants' positions in DFS order before the graph is mutated.
        # This order also guarantees that each ancestor is restored before any
        # element that references it, so insert() calls in restore() always succeed.
        children_positions: List = []
        for desc in graph.collect_all_descendants(trashed_item):
            ref_id, position_type, output = graph.get_position(desc)
            children_positions.append([desc.id, ref_id, position_type, output])

        return {
            "position": list(position_triplet),
            "children": children_positions,
        }

    def trash(self, item_to_trash: Element, requesting_user, trash_entry: TrashEntry):
        page = item_to_trash.page
        super().trash(item_to_trash, requesting_user, trash_entry)
        result = page.get_graph().remove(item_to_trash)

        # Soft-delete children removed by the graph cascade so they can be
        # restored alongside the container. before_delete cleans up related
        # data (workflow actions, menu items, etc.) before we mark them trashed.
        for dep in result.dependencies_removed:
            specific = dep.specific
            specific.get_type().before_delete(specific)
            specific.trashed = True
            specific.save(update_fields=["trashed"])

        element_deleted.send(
            self, element_id=item_to_trash.id, page=page, user=requesting_user
        )
        ElementHandler().invalidate_element_cache(page)

    def restore(self, trashed_item: Element, trash_entry: TrashEntry):
        super().restore(trashed_item, trash_entry)

        data = trash_entry.additional_restoration_data
        if isinstance(data, dict):
            position_triplet = data["position"]
            children_positions = data.get("children", [])
        else:
            # Old-format trash entries (plain list): no children to restore.
            position_triplet = data
            children_positions = []

        reference_element_id, position_type, output = position_triplet
        reference_element = None
        if reference_element_id is not None:
            try:
                reference_element = ElementHandler().get_element(
                    int(reference_element_id)
                )
            except ElementDoesNotExist:
                raise TrashItemRestorationDisallowed(
                    "This element cannot be restored as its reference element "
                    "has been deleted."
                )

        graph = trashed_item.page.get_graph()
        graph.insert(trashed_item, reference_element, position_type, output)

        # Collect restored elements starting with the container itself.
        # .specific is needed because element_type_registry serializers expect
        # the concrete subclass, not the generic Element base instance.
        restored_elements = [trashed_item.specific]

        # Restore children in DFS order (ancestors before their dependants),
        # un-trashing each and re-inserting into the graph at its stored position.
        for child_id, ref_id, child_position_type, child_output in children_positions:
            try:
                child = Element.objects_and_trash.get(id=child_id, trashed=True)
            except Element.DoesNotExist:
                raise TrashItemRestorationDisallowed(
                    f"This element cannot be fully restored because a child element "
                    f"({child_id}) has been permanently deleted."
                )

            child.trashed = False
            child.save(update_fields=["trashed"])

            child_reference = None
            if ref_id is not None:
                child_reference = Element.objects_and_trash.get(id=int(ref_id))

            graph.insert(child, child_reference, child_position_type, child_output)
            restored_elements.append(child.specific)

        ElementHandler().invalidate_element_cache(trashed_item.page)
        elements_created.send(
            self,
            elements=restored_elements,
            page=trashed_item.page,
            user=None,
        )

    def permanently_delete_item(
        self, trashed_item: Element, trash_item_lookup_cache=None
    ):
        # Permanently delete any children that were soft-deleted alongside this
        # container. They have no TrashEntry of their own, so they must be cleaned
        # up here using the IDs we stored in additional_restoration_data.
        try:
            trash_entry = TrashEntry.objects.get(
                trash_item_type=self.type,
                trash_item_id=trashed_item.id,
            )
            data = trash_entry.additional_restoration_data
            if isinstance(data, dict):
                child_ids = [row[0] for row in data.get("children", [])]
                if child_ids:
                    Element.trash.filter(id__in=child_ids).delete()
        except TrashEntry.DoesNotExist:
            pass

        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreElementOperationType.type
