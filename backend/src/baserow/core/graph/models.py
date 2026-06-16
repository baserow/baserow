from typing import TYPE_CHECKING, List, Optional, Self

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import gettext_lazy as _

from baserow.core.cache import local_cache
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import (
    GraphPointPosition,
    GraphPointPositionType,
    SerializedGraph,
)
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.registries import TrashableItemType

if TYPE_CHECKING:
    from baserow.core.models import TrashEntry


class GraphModelMixin(models.Model):
    """
    A mixin that can be used to add a point graph to a model. The graph is stored as
    a JSON field and can be accessed via the get_graph method.
    """

    graph = models.JSONField(
        default=dict,
        db_default={},
        help_text="A JSON serialized graph containing the points and edges.",
    )

    class Meta:
        abstract = True

    def get_graph_handler(self):
        raise NotImplementedError("Subclasses must implement get_graph_handler method.")

    def get_graph(self) -> BaseGraphHandler:
        """
        Returns the shared graph handler for this model's ID within the current
        request.  A single handler is cached per (model_label, id) so that all
        callers within a request see the same in-memory graph mutations.

        If the cached handler was seeded by a *different* Python instance of the
        same row (e.g. a freshly fetched reference_element.page), we rebind it
        to `self` so that mutations remain visible via `self.graph`.
        """

        handler_class = self.get_graph_handler()
        handler = local_cache.get(
            f"cached_graph_{self._meta.label}_{self.id}",
            lambda: handler_class(self),
        )
        if handler.instance is not self:
            # Another page object (same DB row, different Python object) seeded
            # the cache first.  Share the same graph dict so that subsequent
            # mutations made through the handler are visible on self.graph.
            self.graph = handler.instance.graph
            handler.instance = self
        return handler

    def print_graph(self, message=None, original=False):
        """
        Prints the graph in a pretty way. Useful for debug.
        """

        import pprint

        if message:
            print(message)

        if original:
            pprint.pprint(self.get_graph().graph, indent=2)
        else:
            pprint.pprint(self.get_graph().labeled_graph(), indent=2)

    def assert_reference(self, reference: SerializedGraph):
        """
        Used in test, compare the current graph with the given reference and
        raise an error if the graph doesn't match.
        """

        import pprint

        try:
            assert (
                self.get_graph().labeled_graph() == reference  # nosec B101
            ), "Failed to match the reference."
        except AssertionError:
            print("Failed to match the reference:")
            pprint.pprint(reference, indent=2)
            self.print_graph("Current graph:")
            raise


class GraphPointMixin:
    """
    A mixin that can be used to add graph point related methods to a model.

    Classes using this mixin must also inherit from Django's Model and implement
    the GraphPoint protocol (i.e., have `get_parent()` and `get_type()` methods).
    """

    def _get_graph(self) -> BaseGraphHandler:
        """
        A convenience method which return's our parent model
        (which implements the `GraphModelMixin`) graph.

        :return: A graph handler instance related to the parent model.
        """

        return self.get_parent().get_graph()

    @property
    def graph_point_label(self) -> str:
        """
        A convenience method used by the graph handler's `labeled_graph` method.
        If a graph point has a label, then it's used, otherwise we just return
        the model's type name.

        :return: A label which we can show in `labeled_graph`.
        """

        if hasattr(self, "label") and self.label:
            return self.label
        else:
            return self.get_type().type

    def get_previous_edge_name(self) -> str:
        """
        Returns the nearest `next` edge used to reach this point.
        """

        previous_positions = self.get_previous_positions()
        for _previous_point, position, output in reversed(previous_positions):
            if position == GraphPointPosition.SOUTH:
                return output
        return ""

    def get_place_name(self) -> str:
        """
        Returns the nearest parent place used to reach this point.
        """

        previous_positions = self.get_previous_positions()
        for _previous_point, position, output in reversed(previous_positions):
            if position == GraphPointPosition.CHILD:
                return output
        return ""

    def graph_point_edge_label(self, uid: str) -> str:
        """
        A convenience method used by the graph handler's `labeled_graph` method.
        By default, we return an empty string, it's up to `GraphPointMixin` classes
        to determine (if at all) what their point edge labels should be.

        :param uid: The uid of the edge for which we want to get the label.
        :return: A label which we can show in `labeled_graph` for the edge
            with the given uid.
        """

        return _("Unlabeled")

    @property
    def is_root_point(self) -> bool:
        """
        Returns True if the point is a root point in the graph. A root point is
        always at key "0" in the graph and is the starting point of the graph.
        There is only ever one root point.

        :return: True if the point is the root point.
        """

        return self._get_graph().get_point_at_position(None, "south", "").id == self.id

    @property
    def is_nested_point(self) -> bool:
        """
        Returns True if the point is nested in the graph. A nested point is a point
        that is not at the root level of the graph, but is a child of another point
        (or a sibling within a container's next chain).

        :return: True if the point is nested.
        """

        return any(
            position == GraphPointPosition.CHILD
            for _previous_point, position, _output in self.get_previous_positions()
        )

    def get_previous_points(self) -> list[Self]:
        """
        Returns the points before the current point. A previous point can be a
        `previous point` or a `parent point`.
        """

        return [
            previous_point
            for previous_point, _position, _output in self.get_previous_positions()
            if previous_point is not None
        ]

    def get_child_points(self) -> list[Self]:
        """
        Returns the direct children of the given point.
        """

        return self._get_graph().get_children(self)

    def get_sibling_points(self) -> list[Self]:
        """
        Returns the siblings of the given point.
        """

        return self._get_graph().get_siblings(self)

    def get_previous_positions(
        self,
    ) -> list[tuple[Self | None, GraphPointPositionType, str]]:
        """
        Returns the path of graph positions used to reach this point, ordered
        from root to this point. Uses the cached previous-position map so the
        path is resolved with O(depth) dict lookups.
        """

        return self._get_graph().get_previous_positions(self) or []

    def get_parent_point(self) -> Self | None:
        """
        Returns the direct parent container point, or `None` if this point
        has no parent. Uses the cached previous-position map so the chain is
        resolved with O(depth) dict lookups rather than a full graph traversal.
        """

        for previous_point, position, _output in reversed(
            self.get_previous_positions()
        ):
            if position == GraphPointPosition.CHILD:
                return previous_point
        return None

    def get_parent_points(self) -> list[Self]:
        """
        Returns the ancestor container points that contain this point, ordered
        from outermost to innermost (direct parent last). Uses the cached
        previous-position map so the chain is resolved with O(depth) dict
        lookups rather than a full graph traversal per element.
        """

        return [
            previous_point
            for previous_point, position, _output in self.get_previous_positions()
            if position == GraphPointPosition.CHILD
        ]

    def get_next_points(self, output_uid: str | None = None) -> list[Self]:
        """
        Returns all points which directly follow this point in the workflow.
        A list of points is returned as there can be multiple points that follow this one,
        for example when there are multiple branches in the workflow.

        :param output_uid: filter points only for this output uid.
        """

        return self._get_graph().get_next_points(self, output_uid)


class GraphPointTrashableItemType(TrashableItemType):
    """
    A base trashable item type for models that are points in a graph - i.e. they
    inherit `GraphPointMixin` and live inside a parent's `GraphModelMixin`
    graph (builder elements, automation nodes).

    It centralises the graph-aware trash/restore logic:
    - Capturing a point's position (and its descendants') before trashing,
    - Removing it from the graph and soft-deleting any cascaded children on trash,
    - Re-inserting the point and its children at their stored positions on restore.

    Subclasses override `trash` / `restore` to call `super()` and then send
    their own realtime signals and invalidate their own caches. `restore`
    returns the list of restored (`.specific`) records so subclasses can
    broadcast them. The small hooks below (`should_mutate_graph`,
    `before_cascade_delete`, `validate_reference`) cover the per-type
    differences without forcing every subclass to reimplement the algorithm.
    """

    def should_mutate_graph(self, trash_entry: "TrashEntry") -> bool:
        """
        Whether trash/restore should mutate the graph. Defaults to `True`.
        Subclasses whose trash operation rearranges the graph itself (e.g. an
        automation node "replace") return `False` to skip the remove/insert.
        """

        return True

    def before_cascade_delete(self, descendant: "GraphPointMixin"):
        """
        Run on each descendant soft-deleted by the trash cascade, before it is
        marked trashed. Defaults to a no-op: trashing must be fully reversible, so a
        type's owned related data is cleaned up only on permanent deletion (see
        `before_permanent_delete`), never here. Subclasses may override to react to
        the cascade without destroying restorable data.
        """

    def before_permanent_delete(self, item: "GraphPointMixin"):
        """
        Run on the point (and each cascaded child) just before it is permanently
        deleted, so types can clean up owned related data that the database cascade
        won't remove (e.g. a collection element's fields). Defaults to a no-op.

        :param item: The `.specific` instance about to be permanently deleted.
        """

    def validate_reference(self, reference: Optional["GraphPointMixin"], output: str):
        """
        Validate the resolved reference point before re-insertion on restore.
        Defaults to a no-op. Subclasses can override (e.g. to check the reference's
        output/branch still exists).
        """

    def _resolve_reference(
        self, reference_id: Optional[int]
    ) -> Optional["GraphPointMixin"]:
        """
        Resolve the reference point a restored item attaches to, distinguishing a
        permanently deleted reference from a merely trashed one so the user gets an
        actionable message naming what to restore first.
        """

        if reference_id is None:
            return None

        reference = self.model_class.objects_and_trash.filter(id=reference_id).first()
        if reference is None:
            raise TrashItemRestorationDisallowed(
                "This record cannot be restored as its reference record "
                "has been deleted."
            )
        if reference.trashed:
            raise TrashItemRestorationDisallowed(
                f"This record cannot be restored until {reference} "
                f"({reference.id}) is restored first."
            )
        return reference.specific

    def _assert_hierarchical_parent_not_trashed(
        self, hierarchical_parent_id: Optional[int]
    ):
        """
        Refuse restoration when the point's parent point is itself trashed.

        Only the immediate parent needs checking: the graph is a connected tree, so
        a non-trashed parent is guaranteed to be in the graph together with all of
        its own ancestors. The recursion across nesting levels therefore happens
        naturally — restoring a deeply nested point first requires restoring its
        parent, which in turn requires restoring its grandparent, and so on.

        :param hierarchical_parent_id: The id of the parent container, or None.
        :raises TrashItemRestorationDisallowed: If the parent is still trashed.
        """

        if hierarchical_parent_id is None:
            return

        parent = self.model_class.objects_and_trash.filter(
            id=hierarchical_parent_id
        ).first()
        if parent is not None and parent.trashed:
            raise TrashItemRestorationDisallowed(
                f"This record cannot be restored until its parent "
                f"{parent} ({parent.id}) is restored first."
            )

    def get_name(self, trashed_item: "GraphPointMixin") -> str:
        name = f"{trashed_item} ({trashed_item.id})"
        # Mention the parent container (if any) so that, when restoration is blocked
        # because the parent is still trashed, the user can tell which record they
        # need to restore first.
        parent = trashed_item.get_parent_point()
        if parent is not None:
            name += f" inside {parent} ({parent.id})"
        return name.lower()

    def get_additional_restoration_data(self, trashed_item: "GraphPointMixin"):
        graph = trashed_item.get_parent().get_graph()
        position_triplet = graph.get_position(trashed_item)

        # The container this point lives in (None for top-level points). Captured
        # while still in the graph so restore() can refuse if the parent is trashed.
        parent = trashed_item.get_parent_point()

        # Capture all descendants' positions in DFS order before the graph is
        # mutated. This order also guarantees that each ancestor is restored before
        # any point that references it, so insert() calls in restore() succeed.
        children_positions: List = []
        for desc in graph.collect_all_descendants(trashed_item):
            ref_id, position_type, output = graph.get_position(desc)
            children_positions.append([desc.id, ref_id, position_type, output])

        return {
            "position": list(position_triplet),
            "hierarchical_parent_id": parent.id if parent is not None else None,
            "children": children_positions,
        }

    def _parse_restoration_data(self, data):
        """
        Read the position triplet, children and hierarchical parent from the stored
        restoration data, tolerating the legacy bare-tuple shape (old automation
        entries) which only carried the position.
        """

        if isinstance(data, dict):
            return (
                data["position"],
                data.get("children", []),
                data.get("hierarchical_parent_id"),
            )
        return data, [], None

    def trash(
        self,
        item_to_trash: "GraphPointMixin",
        requesting_user,
        trash_entry: "TrashEntry",
    ) -> List["GraphPointMixin"]:
        """
        Trash the point and (unless the graph is left untouched) the subtree it
        cascades to.

        :return: The definitive set of records that were trashed, as `.specific`
            instances, starting with the point itself followed by any cascaded
            descendants in DFS order. Mirrors `restore`, which returns the same
            shape for the records it brings back, so subclasses can broadcast the
            full set without recomputing the cascade.
        """

        super().trash(item_to_trash, requesting_user, trash_entry)

        if not self.should_mutate_graph(trash_entry):
            return [item_to_trash.specific]

        result = item_to_trash.get_parent().get_graph().remove(item_to_trash)

        # Soft-delete children removed by the graph cascade so they can be restored
        # alongside their container.
        for dep in result.dependencies_removed:
            specific = dep.specific
            self.before_cascade_delete(specific)
            specific.trashed = True
            specific.save(update_fields=["trashed"])

        return [
            item_to_trash.specific,
            *(dep.specific for dep in result.dependencies_removed),
        ]

    def restore(self, trashed_item: "GraphPointMixin", trash_entry: "TrashEntry"):
        position_triplet, children_positions, hierarchical_parent_id = (
            self._parse_restoration_data(trash_entry.additional_restoration_data)
        )

        mutate_graph = self.should_mutate_graph(trash_entry)
        if mutate_graph:
            # Block restoration up-front (before un-trashing) when the parent
            # container is still trashed, naming the record to restore first.
            self._assert_hierarchical_parent_not_trashed(hierarchical_parent_id)

        super().restore(trashed_item, trash_entry)

        # Collect restored records starting with the point itself. .specific is
        # needed because type registry serializers expect the concrete subclass.
        restored_records = [trashed_item.specific]
        if not mutate_graph:
            return restored_records

        reference_id, position_type, output = position_triplet
        reference = self._resolve_reference(reference_id)
        self.validate_reference(reference, output)

        graph = trashed_item.get_parent().get_graph()
        graph.insert(trashed_item, reference, position_type, output)

        # Restore children in DFS order (ancestors before their dependants),
        # un-trashing each and re-inserting into the graph at its stored position.
        for child_id, ref_id, child_position_type, child_output in children_positions:
            try:
                child = self.model_class.objects_and_trash.get(
                    id=child_id, trashed=True
                )
            except ObjectDoesNotExist:
                raise TrashItemRestorationDisallowed(
                    f"This record cannot be fully restored because a child record "
                    f"({child_id}) has been permanently deleted."
                )

            child.trashed = False
            child.save(update_fields=["trashed"])

            child_reference = None
            if ref_id is not None:
                child_reference = self.model_class.objects_and_trash.get(id=int(ref_id))

            graph.insert(child, child_reference, child_position_type, child_output)
            restored_records.append(child.specific)

        return restored_records

    def permanently_delete_item(self, trashed_item, trash_item_lookup_cache=None):
        from baserow.core.models import TrashEntry

        # Permanently delete any children that were soft-deleted alongside this
        # container. They have no TrashEntry of their own, so they must be cleaned
        # up here using the IDs we stored in additional_restoration_data.
        child_ids: List[int] = []
        try:
            trash_entry = TrashEntry.objects.get(
                trash_item_type=self.type,
                trash_item_id=trashed_item.id,
            )
            data = trash_entry.additional_restoration_data
            if isinstance(data, dict):
                child_ids = [row[0] for row in data.get("children", [])]
        except TrashEntry.DoesNotExist:
            pass

        children = list(self.model_class.trash.filter(id__in=child_ids))

        # Clean up owned related data (e.g. collection fields) now, at permanent
        # deletion. This is intentionally not done at trash time so a restore can
        # bring the item back intact.
        self.before_permanent_delete(trashed_item.specific)
        for child in children:
            self.before_permanent_delete(child.specific)

        if child_ids:
            self.model_class.trash.filter(id__in=child_ids).delete()

        trashed_item.delete()
