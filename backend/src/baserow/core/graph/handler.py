from abc import ABC, abstractmethod
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from django.db import models, transaction

from baserow.core.cache import local_cache
from baserow.core.graph.exceptions import (
    GraphPointDoesNotExist,
    GraphPointNotFoundInGraph,
    GraphPointReferencePointInvalid,
)
from baserow.core.graph.types import (
    GraphModelInstance,
    GraphPoint,
    GraphPointPosition,
    GraphPointPositionTriplet,
    GraphPointPositionType,
    GraphPointRemoved,
    SerializedGraph,
)

if TYPE_CHECKING:
    from baserow.core.graph.models import GraphPointMixin


def _replace(list_, item_to_replace, replacement):
    index = list_.index(item_to_replace)

    return (
        list_[:index]
        + (replacement if isinstance(replacement, list) else [replacement])
        + list_[index + 1 :]
    )


class BaseGraphHandler(ABC):
    """
    The base handler to support all automation workflow and application builder graph
    operations. Most operation over the graph structure should happen here.

    The structure looks like:

    ```
    {
        GRAPH_ROOT_KEY: 1,
        "1": {"next": {"": [2]}},
        "2": {
            "next": {
                "uuid1": [3],
                "uuid2": [5],
                "": [4],
            }
        },
        "3": {},
        "5": {},
        "4": {"next": {"": [6]}},
        "6": {"children": {"": [7], "0": [8], "1": [9]}},
        "7": {},
        "8": {},
        "9": {"next": {"": [10]}},
        "10": {}
    }
    ```

    The key is the ID of a point, except for the key '0' that indicates the ID of the
    first point of the graph.

    For each point, `next` is the dict keyed by edge UUIDs and valued by the list of
    point ID on this edge. For now only one point is possible per output.

    `children` is a dict keyed by edge/place identifiers and valued by lists of child
    point IDs. This allows container elements to have children at different "places"
    (e.g., different columns or slots). The "" (empty string) key represents the
    default edge.

    For backwards compatibility, `children` may also be a simple array (legacy format):
    `{"children": [7]}` is treated as `{"children": {"": [7]}}`.

    This graph structure uses triplets to identify the position of a point.
    A triplet looks like [reference_point, position, output].

    For instance:
    - [<Point(42)>, 'south', ''] refers to the point placed at the
      south of the point 42 at default output "".
    - [<Point(42)>, 'south', 'uuid45'] refers to the point placed at the
      south of the point 42 at the edge with uid `uuid45`.
    - [<Point(42)>, 'child', ''] refers to the point placed as child of the
      point 42 at the default edge.
    - [<Point(42)>, 'child', '0'] refers to the point placed as child of the
      point 42 at edge/place "0".
    """

    # The key in the graph which denotes that it's the 'first'
    # or 'root' of the graph. This is not a point ID.
    GRAPH_ROOT_KEY = "0"

    outputs_id_mapping: str = ""
    instance_id_mapping: str = ""
    does_not_exist_exception = GraphPointDoesNotExist
    base_point_class: Type["GraphPointMixin"] = None

    def __init__(self, instance: GraphModelInstance):
        self.instance = instance
        self._instance_locked = False

    @property
    def graph(self) -> SerializedGraph:
        return self.instance.graph

    def _lock_instance_for_update(self):
        """
        Take a row lock on the container before mutating its graph, and refresh
        the in-memory graph from the locked row.

        The graph is a single JSON document written back whole by every
        mutation; without a lock, two concurrent transactions read-modify-write
        it last-writer-wins, silently resurrecting or discarding each other's
        changes (the root cause of the self-reference and ghost-point
        corruptions). The refresh re-synchronises this request's in-memory copy
        with the latest committed state once the lock is held.

        The refresh mutates the existing graph dict in place (rather than
        rebinding it) so that every object sharing it — see
        `GraphModelMixin.get_graph`'s rebinding — observes the refreshed state.

        Locking is skipped for non-model instances (test doubles) and outside
        an atomic block, where `SELECT FOR UPDATE` is either unsupported or
        meaningless (each statement would commit and release immediately).
        """

        if self._instance_locked or not isinstance(self.instance, models.Model):
            return

        if not transaction.get_connection().in_atomic_block:
            return

        locked = (
            type(self.instance)
            ._base_manager.select_for_update()
            .only("graph")
            .get(pk=self.instance.pk)
        )
        current_graph = self.instance.graph
        current_graph.clear()
        current_graph.update(locked.graph)
        local_cache.delete(self.generate_previous_position_map_cache_key(self.instance))
        self._instance_locked = True

    def lock_for_update(self):
        """
        Public entry point to take the container row lock (and refresh the
        in-memory graph) ahead of time — e.g. so a service can validate its
        inputs against the latest committed state before mutating. Idempotent
        per handler instance; the later mutation-time locks become no-ops.
        """

        self._lock_instance_for_update()

    @staticmethod
    def lock_all_for_update(handlers: List["BaseGraphHandler"]):
        """
        Lock several graph containers in a deterministic (ascending pk) order,
        so that two transactions locking the same pair of containers can never
        acquire them in opposite orders and deadlock (e.g. two simultaneous
        cross-graph moves in opposite directions).

        :param handlers: The graph handlers whose containers should be locked.
        """

        def lock_order(handler: "BaseGraphHandler"):
            instance = handler.instance
            return getattr(instance, "pk", None) or getattr(instance, "id", 0) or 0

        for handler in sorted(handlers, key=lock_order):
            handler._lock_instance_for_update()

    def _update_graph(self, graph: Optional[SerializedGraph] = None):
        """
        Responsible for updating the instance's `graph` field. If `graph` is provided,
        it will update the instance with it, otherwise it will update it with the
        current graph.

        :param graph: The new graph to set on the instance.
            If None, it will use the current graph.
        """

        if graph is not None:
            self.instance.graph = graph

        self.instance.save(update_fields=["graph"])
        local_cache.delete(self.generate_previous_position_map_cache_key(self.instance))

    def get_info(self, point: GraphPoint | str | int | None) -> Dict[str, Any]:
        """
        Get the info dict of the given point. The info dict contains the "next" and
        "children" keys that describe the point position in the graph. If the point is
        `None`, it will return the info dict of the root (first point of the graph).

        :param point: The point to get the info dict from. Can be a point instance, a
            point ID or None (to get the info dict of the root).
        :return: The info dict of the given point.
        """

        if point is None:
            point_id = self.graph[self.GRAPH_ROOT_KEY]

        elif hasattr(point, "id"):
            point_id = point.id
        else:
            point_id = point

        return self.graph[str(point_id)]

    def _get_children_dict(
        self, point_info: Dict[str, Any]
    ) -> Dict[str, List[int | str]]:
        """
        For backwards compatibility, get the children as a dict,
        normalizing from the legacy array format if needed.

        Supports both formats:
        - Legacy: {"children": [7, 8]} -> {"": [7, 8]}
        - New: {"children": {"": [7], "0": [8]}} -> {"": [7], "0": [8]}

        :param point_info: The info dict of a point.
        :return: A dict mapping edge keys to lists of child IDs.
        """

        children = point_info.get("children")
        if children is None:
            return {}
        if isinstance(children, list):
            # Legacy format: convert to dict with default edge
            return {"": children} if children else {}
        # New format: already a dict
        return children

    def _get_all_children_ids(self, point_info: Dict[str, Any]) -> List[int | str]:
        """
        Get all children IDs regardless of edge, handling both legacy and new formats.

        :param point_info: The info dict of a point.
        :return: A flat list of all child IDs.
        """

        children_dict = self._get_children_dict(point_info)
        return [cid for child_list in children_dict.values() for cid in child_list]

    def _set_children(
        self,
        point_info: Dict[str, Any],
        edge: str,
        child_ids: List[int | str],
    ):
        """
        Set the children for a specific edge, using the new dict format.

        :param point_info: The info dict of a point to modify.
        :param edge: The edge key (e.g., "", "0", "1").
        :param child_ids: The list of child IDs for this edge.
        """

        if "children" not in point_info or isinstance(point_info["children"], list):
            # Convert from legacy format or initialize
            existing = point_info.get("children", [])
            if isinstance(existing, list) and existing:
                point_info["children"] = {"": existing}
            else:
                point_info["children"] = {}

        if child_ids:
            point_info["children"][edge] = child_ids
        elif edge in point_info["children"]:
            del point_info["children"][edge]

        # Clean up empty children dict
        if not point_info["children"]:
            del point_info["children"]

    @abstractmethod
    def get_point_map(self) -> Dict[int, GraphPoint]:
        """
        Must be implemented by child classes. This method should return an object
        mapping, where the key is the graph point's ID, and the value is the model
        instance.
        """
        ...

    def get_point(self, point_id: str | int) -> GraphPoint:
        """
        Given a graph point, return the corresponding model instance from the point map.

        :param point_id: The ID of the graph point to retrieve.
        :return: The model instance corresponding to the given graph point ID.
        """

        if int(point_id) not in self.get_point_map():
            raise self.does_not_exist_exception(point_id)

        return self.get_point_map()[int(point_id)]

    def get_point_at_position(
        self,
        reference_point: GraphPoint,
        position: GraphPointPositionType,
        output: str,
    ) -> GraphPoint | None:
        """
        Returns the point at the given position in the graph.

        :param reference_point: The point used as reference for the position.
        :param position: The direction relative to the reference point.
        :param output: The output of the reference point to use.
        """

        output = "" if output is None else str(output)

        if position == "south":
            # First point
            if reference_point is None:
                if self.GRAPH_ROOT_KEY in self.graph:
                    return self.get_point(self.graph[self.GRAPH_ROOT_KEY])
                else:
                    return None

            next_points = self.get_info(reference_point).get("next", {}).get(output, [])
            if next_points:
                return self.get_point(next_points[0])

        elif position == "child":
            children_dict = self._get_children_dict(self.get_info(reference_point))
            children = children_dict.get(output, [])
            if children:
                return self.get_point(children[0])

        return None

    def get_last_position(self) -> GraphPointPositionTriplet:
        """
        Return the last position of the graph if we follow the default edge ("") of
        each point. Mostly used to place points in tests.
        """

        if self.graph.get(self.GRAPH_ROOT_KEY) is None:
            return None, "south", ""

        point_id = self.graph[self.GRAPH_ROOT_KEY]
        seen_ids = {int(point_id)}
        while True:
            next_points = self.get_info(point_id).get("next", {}).get("", [])
            unseen_next_points = [
                next_id for next_id in next_points if int(next_id) not in seen_ids
            ]
            if not unseen_next_points:
                return self.get_point(point_id), "south", ""
            point_id = unseen_next_points[0]
            seen_ids.add(int(point_id))

    def append(self, point: GraphPoint) -> None:
        """
        Insert a point at the end of the default edge chain.
        """

        # Lock before computing the position: "the end of the chain" must be
        # resolved against the latest committed graph, not a stale read taken
        # before a concurrent transaction appended its own point.
        self._lock_instance_for_update()
        ref, position, output = self.get_last_position()
        self.insert(point, ref, position, output)

    def get_position(self, point: GraphPoint) -> GraphPointPositionTriplet:
        """
        Return the position of the given point in the graph as a triplet of
        `[reference_point, position, output]`.

        :param point: The point to get the position from.
        :return: A triplet of `[reference_point, position, output]` describing the
            position of the given point in the graph. If the point is the root point,
            it will return `(None, "north", "")`.

            The root is reported as `"north"` (not `"south"`) deliberately: this
            triplet has to round-trip back through `move`/`insert` (e.g. to undo a
            move of the first element). `insert(reference=None, ...)` always places
            the point at the root, but `move` treats the specific `(None, "south")`
            pair as "append to the end of the chain" (used by the orphan-undo path).
            Returning `(None, "north", "")` therefore restores the root via insert,
            while leaving `(None, "south", "")` free to mean "append".
        :raises GraphPointNotFoundInGraph: If the point is not found in the graph.
        """

        # Is it the root point?
        if point.id == self.graph.get(self.GRAPH_ROOT_KEY, None):
            return None, GraphPointPosition.NORTH, ""

        for point_id, point_info in self.graph.items():
            if point_id == self.GRAPH_ROOT_KEY or point_id == str(point.id):
                continue

            for output_uid, next_points in point_info.get("next", {}).items():
                if point.id in next_points:
                    return point_id, "south", output_uid

            children_dict = self._get_children_dict(point_info)
            for edge_key, child_ids in children_dict.items():
                if point.id in child_ids:
                    return point_id, "child", edge_key

        raise GraphPointNotFoundInGraph(f"Point {point.id} not found in the graph")

    def get_previous_positions(
        self, target_point: GraphPoint
    ) -> List[GraphPointPositionTriplet] | None:
        """
        Given a `GraphPoint`, generates the list of all positions to get to the
        target `GraphPoint`. The positions are represented as a list of triplets of
        `[reference_point, position, output]`.

        :param target_point: The point to get the positions to.
        :return: A list of triplets of `[reference_point, position, output]` describing
            the positions to get to the target point. If the target point is not found
            in the graph, it will return `None`.
        """

        previous_position_map = self.get_previous_position_map()
        positions = []
        current_id = target_point.id
        found = False
        seen_ids: set[int] = set()
        while previous_position := previous_position_map.get(current_id):
            if current_id in seen_ids:
                # A corrupted graph can make a point (transitively) its own
                # predecessor; stop instead of walking the cycle forever.
                break
            seen_ids.add(current_id)
            found = True
            reference_id, position, output = previous_position
            if reference_id is None:
                break
            reference_point = (
                self.get_point(reference_id) if reference_id is not None else None
            )
            positions.append((reference_point, position, output))
            current_id = reference_id

        if not found:
            return None

        return list(reversed(positions))

    def _get_all_next_points(self, point: GraphPoint) -> List[str]:
        """
        Get all next points of the given point, regardless of the output.

        :param point: The point to get the next points from.
        :return: A list of all next points of the given point.
        """

        point_info = self.get_info(point)
        return [x for sublist in point_info.get("next", {}).values() for x in sublist]

    def get_next_points(
        self, point: GraphPoint, output: str | None = None
    ) -> List[GraphPoint]:
        """
        Get the next points of the given point for the given output. If output is
        `None`, it will return the next points for all outputs.

        :param point: The point to get the next points from.
        :param output: The output to get the next points for. If `None`, it
            will return the next points for all outputs.
        """

        point_info = self.get_info(point)
        return [
            self.get_point(x)
            for uid, sublist in point_info.get("next", {}).items()
            for x in sublist
            if output is None or uid == output
        ]

    def get_children(
        self,
        point: GraphPoint | int,
        output: str | None = None,
        first_only: bool = False,
    ) -> List[GraphPoint] | List[int]:
        """
        Get the children of the given point.

        :param point: The point (a model instance, or the ID of the point) to
            get the children from.
        :param output: The edge/place to get children for. If `None`, returns
            children from all edges.
        :param first_only: When True, return only the entry-point child of each
            edge/slot without following the next[""] chain within slots. Use this
            when the caller will handle chaining via get_next_points itself.
        :return: A list of children of the given point.
        """

        if point is None:
            point_id = self.graph[self.GRAPH_ROOT_KEY]
        elif hasattr(point, "id"):
            point_id = point.id
        else:
            point_id = point

        point_info = self.get_info(point)
        children_dict = self._get_children_dict(point_info)
        result = []
        # Seeded with the container itself and shared across all edges/slots so
        # that even on a corrupted graph no point is ever traversed twice.
        seen: set[int] = {int(point_id)}
        for edge_key, child_ids in children_dict.items():
            if output is not None and edge_key != output:
                continue
            for cid in child_ids:
                if first_only:
                    result.append(self.get_point(cid))
                else:
                    result.extend(self._get_chain_elements(cid, seen))
        return result

    @classmethod
    def generate_previous_position_map_cache_key(
        cls, graph_model: GraphModelInstance
    ) -> str:
        return f"previous_position_map_{graph_model._meta.label}_{graph_model.id}"

    def get_previous_position_map(
        self,
    ) -> Dict[int, tuple[int | None, GraphPointPositionType, str]]:
        """
        Returns the cached mapping of each point ID to its immediate incoming
        graph position.
        """

        return local_cache.get(
            self.generate_previous_position_map_cache_key(self.instance),
            lambda: self.build_previous_position_map(self.graph),
        )

    @classmethod
    def _get_children_dict_from_info(
        cls, point_info: Dict[str, Any]
    ) -> Dict[str, List[int | str]]:
        children = point_info.get("children")
        if children is None:
            return {}
        if isinstance(children, list):
            return {"": children} if children else {}
        return children

    @classmethod
    def build_previous_position_map(
        cls, graph: SerializedGraph | None
    ) -> Dict[int, tuple[int | None, GraphPointPositionType, str]]:
        """
        Build and return a mapping of `{point_id: incoming_position}` for every
        point in the graph, including the root.

        :param graph: A raw serialized graph dict (maybe `None`).
        :return: A dict mapping each point ID to the immediate position that
            reaches it as `(reference_point_id, position, output)`.
        """

        previous_position_map: Dict[
            int, tuple[int | None, GraphPointPositionType, str]
        ] = {}
        if graph and cls.GRAPH_ROOT_KEY in graph:
            previous_position_map[int(graph[cls.GRAPH_ROOT_KEY])] = (
                None,
                GraphPointPosition.SOUTH,
                "",
            )

        for str_id, info in (graph or {}).items():
            if str_id == cls.GRAPH_ROOT_KEY or not isinstance(info, dict):
                continue

            reference_id = int(str_id)
            for output, next_ids in info.get("next", {}).items():
                for next_id in next_ids:
                    previous_position_map[int(next_id)] = (
                        reference_id,
                        GraphPointPosition.SOUTH,
                        output,
                    )

            children_dict = cls._get_children_dict_from_info(info)
            for output, child_ids in children_dict.items():
                if child_ids:
                    previous_position_map[int(child_ids[0])] = (
                        reference_id,
                        GraphPointPosition.CHILD,
                        output,
                    )

        return previous_position_map

    def _walk_chain_ids(self, first_id: str | int, seen: set[int]) -> List[str]:
        """
        Follow the default next[""] chain from first_id and return the string IDs
        of the visited points, in order. Every visited point is added to `seen`,
        which callers can share across multiple walks (e.g. the slots of a
        container) so that no point is ever visited twice and the walk always
        terminates, even on a corrupted graph (e.g. a point whose `next` loops
        back onto itself or an ancestor).

        The walk never mutates the graph: repairing corruption is the
        responsibility of the healing process (e.g. the builder's
        `heal_corrupted_graph`); a walk just refuses to follow a reference to
        an already-seen point.

        :param first_id: The starting point ID.
        :param seen: The set of point IDs already visited by the wider
            traversal; mutated in place.
        :return: Ordered list of the string IDs in the chain.
        """

        result: List[str] = []
        current = str(first_id) if int(first_id) not in seen else None
        while current is not None:
            seen.add(int(current))
            result.append(current)

            next_ids = self.graph.get(current, {}).get("next", {}).get("", [])
            unseen_next_ids = [nid for nid in next_ids if int(nid) not in seen]
            current = str(unseen_next_ids[0]) if unseen_next_ids else None

        return result

    def _get_chain_tail_id(self, first_id: str | int) -> str:
        """
        Follow the default next[""] chain from first_id and return the string ID of
        the last element — the one that has no next[""] successor.

        :param first_id: The starting point ID.
        :return: String ID of the tail element.
        """

        return self._walk_chain_ids(first_id, set())[-1]

    def _get_chain_elements(
        self, first_id: str | int, seen: Optional[set[int]] = None
    ) -> List[GraphPoint]:
        """
        Collect all graph points reachable via the default next[""] chain from
        first_id, in order.

        :param first_id: The starting point ID.
        :param seen: Optionally, the set of point IDs already visited by the
            wider traversal (mutated in place); those points are not visited
            again.
        :return: Ordered list of all points in the chain.
        """

        chain_ids = self._walk_chain_ids(first_id, seen if seen is not None else set())
        return [self.get_point(int(point_id)) for point_id in chain_ids]

    def get_descendants(self, point: GraphPoint) -> List[GraphPoint]:
        """
        Returns all descendants (direct and transitive children) of the given
        point in depth-first order.

        :param point: The point whose descendants should be collected.
        :return: The list of descendant points.
        """

        return self.collect_all_descendants(point)

    def collect_all_descendants(self, point: GraphPoint) -> List[GraphPoint]:
        """
        Returns all descendants (direct and transitive children) of a point in
        depth-first order, by recursing into each child returned by get_children.
        Every point is returned at most once so corrupted cycles terminate.
        """

        seen_ids = {point.id}

        def collect(current_point):
            result = []
            for child in self.get_children(current_point):
                if child.id in seen_ids:
                    continue
                seen_ids.add(child.id)
                result.append(child)
                result.extend(collect(child))
            return result

        return collect(point)

    def collect_descendant_ids(self, point_id: int) -> set[int]:
        """
        Returns the ids of every point inside the given point's subtree — its
        children (all edges) and everything reachable from them through `next`
        (all outputs) and further `children`. A pure serialized-graph walk with
        a seen set (no model resolution, no queries), so it terminates even on
        a corrupted graph and is cheap enough to run as a write-time guard.

        :param point_id: The id of the point whose subtree should be walked.
        :return: The ids of the subtree's points (the point itself excluded).
        """

        graph = self.graph
        seen: set[int] = {int(point_id)}
        stack: List[int] = []

        info = graph.get(str(point_id))
        if isinstance(info, dict):
            for child_ids in self._get_children_dict_from_info(info).values():
                stack.extend(int(child_id) for child_id in child_ids)

        result: set[int] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            result.add(current)
            info = graph.get(str(current))
            if not isinstance(info, dict):
                continue
            for next_ids in info.get("next", {}).values():
                stack.extend(int(next_id) for next_id in next_ids)
            for child_ids in self._get_children_dict_from_info(info).values():
                stack.extend(int(child_id) for child_id in child_ids)

        return result

    def _has_incoming_references(self, point_id: int) -> bool:
        """
        Return whether any point in the graph (or the root pointer) references
        the given point via `next` or `children`. The point's own entry is
        ignored: a corrupted self-reference is `strip_self_references`'
        responsibility, not a reason to treat the point as placed.

        :param point_id: The id to look up incoming references for.
        :return: True when at least one incoming reference exists.
        """

        graph = self.graph
        if graph.get(self.GRAPH_ROOT_KEY) == point_id:
            return True
        for key, info in graph.items():
            if (
                key == self.GRAPH_ROOT_KEY
                or int(key) == int(point_id)
                or not isinstance(info, dict)
            ):
                continue
            for next_ids in info.get("next", {}).values():
                if point_id in next_ids:
                    return True
            for child_ids in self._get_children_dict_from_info(info).values():
                if point_id in child_ids:
                    return True
        return False

    def merge_children_into_place(
        self,
        container_point: GraphPoint,
        from_places: List[str],
        to_place: str,
    ) -> List[GraphPoint]:
        """
        Moves the children chains from each place in from_places into to_place
        within the same container, appending them to the end of to_place's existing
        chain. The from_places entries are removed from the container's children dict.

        Used when a container loses columns/slots and its occupants must be
        consolidated into a surviving place.

        :param container_point: The container whose children are being reorganised.
        :param from_places: The place keys being removed; their chains are appended
            to to_place in order.
        :param to_place: The surviving place key that will receive the moved children.
        :return: All GraphPoint instances that were moved (in chain order, per place).
        """

        self._lock_instance_for_update()

        from_places = [str(p) for p in from_places]
        to_place = str(to_place)

        container_info = self.get_info(container_point)
        children_dict = self._get_children_dict(container_info)

        # Find the current tail of to_place (None means to_place is currently empty).
        to_place_head = children_dict.get(to_place, [])
        current_tail_id: str | None = (
            self._get_chain_tail_id(to_place_head[0]) if to_place_head else None
        )

        moved: List[GraphPoint] = []

        for place in from_places:
            from_head = children_dict.get(place, [])
            if not from_head:
                continue

            first_id = from_head[0]
            moved.extend(self._get_chain_elements(first_id))

            if current_tail_id is not None:
                # Attach the from-chain after the current tail.
                self.graph[current_tail_id].setdefault("next", {})[""] = [first_id]
            else:
                # to_place was empty — make this chain its first child.
                self._set_children(container_info, to_place, [first_id])

            current_tail_id = self._get_chain_tail_id(first_id)

            # Remove the vacated place from the container.
            self._set_children(container_info, place, [])

        self._update_graph()
        return moved

    def get_siblings(self, point: GraphPoint) -> List[GraphPoint]:
        """
        Get the siblings of the given point. Siblings are points that share the same
        parent and are on the same edge/place.

        :param point: The point to get the siblings from.
        :return: A list of siblings of the given point.
        """

        # Walk back through the ancestry to find the nearest container parent.
        # Elements chained via next[""] inside a container have position "south",
        # so we can't just check the direct position — we need to find the
        # container and edge via get_previous_positions.
        previous_positions = self.get_previous_positions(point)
        if not previous_positions:
            return []

        # Find the nearest "child" position in the ancestry — that tells us
        # which container and edge this point belongs to.
        container_point_id = None
        edge_key = None
        for prev_point, position, output in reversed(previous_positions):
            if position == "child":
                container_point_id = prev_point
                edge_key = output
                break

        if container_point_id is None:
            return []

        # Get all children on the same edge (following next[""] chains)
        container_info = self.get_info(container_point_id)
        children_dict = self._get_children_dict(container_info)
        head_ids = children_dict.get(edge_key, [])

        all_on_edge = []
        for head_id in head_ids:
            all_on_edge.extend(self._get_chain_elements(head_id))

        return [p for p in all_on_edge if p.id != point.id]

    def insert(
        self,
        point: GraphPoint,
        reference_point: GraphPoint,
        position: GraphPointPositionType,
        output: Optional[str] = "",
    ):
        """
        Insert a point at the given position in the graph. The position is described by
        the `reference_point`, the `position` and the `output`. For instance, if the
        position is `("south", "")`, it will insert the point at the south of the
        reference point at the default output. If the position is `("child", "")`, it
        will insert the point as child of the reference point.
        """

        # Coerce to a string (the output may be a UUID), treating None as the
        # default "" edge. Without the None guard, str(None) would persist a bogus
        # "None" slot key into the graph (e.g. from a move with a null
        # place_in_container).
        output = "" if output is None else str(output)

        self._lock_instance_for_update()

        if reference_point is not None and reference_point.id == point.id:
            raise GraphPointReferencePointInvalid(
                f"Point {point.id} cannot be inserted relative to itself."
            )

        graph = self.graph

        # The reference must actually be keyed in the (just refreshed) graph.
        # A live row that isn't keyed — e.g. an element deleted by a concurrent
        # transaction after the caller fetched it, or an orphan that hasn't
        # been healed yet — has no entry to splice into; proceeding would
        # either KeyError midway or write a reference no traversal can follow.
        if reference_point is not None and str(reference_point.id) not in graph:
            raise GraphPointReferencePointInvalid(
                f"Point {point.id} cannot be inserted relative to point "
                f"{reference_point.id}, which is not in the graph."
            )

        # Inserting a point that the graph already references — through the
        # root pointer or any `next`/`children` reference, at any position —
        # is a double insert: the old reference survives next to the new one,
        # leaving the point with two incoming references (or, when the
        # insertion resolves against the point itself, a self-reference).
        # This state is reachable through concurrent transactions (e.g. a
        # stale write resurrecting a reference that a trash had removed,
        # followed by a restore) and through a move of a "ghost" point whose
        # entry a stale write dropped while a reference to it survived
        # (`remove` then splices nothing). Reject it loudly so the transaction
        # rolls back instead of persisting a corrupted graph.
        if self._has_incoming_references(point.id):
            raise GraphPointReferencePointInvalid(
                f"Point {point.id} is already referenced in the graph; "
                f"inserting it again would corrupt the graph."
            )

        # A reference inside the point's own subtree would make the point its
        # own transitive successor: the reference would gain a `next` or
        # `children` entry pointing back at its own ancestor — a cycle. This
        # is reachable through a move whose caller resolved the reference from
        # stale state (e.g. a client that doesn't yet know the reference was
        # moved into the point being dragged).
        if (
            reference_point is not None
            and reference_point.id in self.collect_descendant_ids(point.id)
        ):
            raise GraphPointReferencePointInvalid(
                f"Point {point.id} cannot be inserted relative to point "
                f"{reference_point.id}, which is inside its own subtree."
            )

        new_next = None

        # If the `reference_point` is `None`, it means that we want to insert the
        # point at the root of the graph. In this case, we need to update the root
        # of the graph to point to the new point, and make the old root (if it exists)
        # a child of the new point.
        if reference_point is None:
            point_info = graph.setdefault(str(point.id), {})
            if self.GRAPH_ROOT_KEY in graph:
                new_next = [graph[self.GRAPH_ROOT_KEY]]

            # Our `point` is now the root of the graph.
            graph[self.GRAPH_ROOT_KEY] = point.id

            if new_next:
                point_info["next"] = {"": new_next}

            self._update_graph()
            return

        if position == "north":
            # Insert the point before the reference point. The new point takes
            # the reference point's position, and the reference point becomes
            # the new point's next on the default output.
            # Resolve the reference's position BEFORE creating the point's
            # graph entry: get_position can raise, and mutating first would
            # leave a detached `{}` entry behind for any caller that catches
            # the exception and carries on.
            ref_position_id, ref_position, ref_output = self.get_position(
                reference_point
            )
            point_info = graph.setdefault(str(point.id), {})

            # If the reference itself has no reference ID, then it's the root.
            # We'll then replace the root with our new `point`.
            if ref_position_id is None:
                graph[self.GRAPH_ROOT_KEY] = point.id
            elif ref_position == "south":
                self.get_info(ref_position_id)["next"][ref_output] = _replace(
                    self.get_info(ref_position_id)["next"][ref_output],
                    reference_point.id,
                    point.id,
                )
            elif ref_position == "child":
                # Get existing children for this edge and replace the reference point
                ref_info = self.get_info(ref_position_id)
                children_dict = self._get_children_dict(ref_info)
                children_on_edge = children_dict.get(ref_output, [])
                new_children = _replace(children_on_edge, reference_point.id, point.id)
                self._set_children(ref_info, ref_output, new_children)

            point_info["next"] = {"": [reference_point.id]}

            self._update_graph()
            return

        point_info = graph.setdefault(str(point.id), {})

        if position == "south":
            if output in self.get_info(reference_point).get("next", {}):
                new_next = self.get_info(reference_point)["next"][output]

            self.get_info(reference_point).setdefault("next", {})[output] = [point.id]

        elif position == "child":
            ref_info = self.get_info(reference_point)
            children_dict = self._get_children_dict(ref_info)

            # The new point always becomes the *head* of the slot's children
            # chain; the previous head (if any) becomes the new point's next on
            # the default edge. This mirrors `get_position`, which only ever
            # reports `(ref, "child", output)` for the head child (subsequent
            # children are `(prev_sibling, "south", "")`), so prepending keeps
            # insert the faithful inverse of get_position — required for move
            # undo/redo to round-trip. It also matches the frontend's
            # `_insertAt('child')`, keeping the optimistic graph consistent.
            if output in children_dict:
                new_next = children_dict[output]
            self._set_children(ref_info, output, [point.id])

        if new_next:
            point_info["next"] = {"": new_next}
        else:
            if "next" in point_info:
                del point_info["next"]

        self._update_graph()

    def remove(
        self, point_to_delete: GraphPoint, keep_info: bool = False
    ) -> GraphPointRemoved:
        """
        Remove the given point from the graph.

        When keep_info is False (the default), any children of the point are also
        removed from the graph — their graph info entries are deleted and returned as
        dependencies_removed so the caller can clean up the corresponding DB records.

        When keep_info is True (used by move), the point's info dict is preserved and
        its children travel with it; no cascade occurs.

        :param point_to_delete: The point to delete.
        :param keep_info: doesn't delete the info dict from the graph yet if True.
        :return: A GraphPointRemoved with point_removed and dependencies_removed.
        """

        self._lock_instance_for_update()
        graph = self.instance.graph

        if str(point_to_delete.id) not in graph:
            # The point is already removed. Could be by a replacement.
            return GraphPointRemoved(point_removed=point_to_delete)

        dependencies: List[GraphPoint] = []
        if not keep_info:
            # Collect all descendants before touching the graph so that the traversal
            # traversal still has access to the full graph structure.
            dependencies = self.collect_all_descendants(point_to_delete)
            for dep in dependencies:
                graph.pop(str(dep.id), None)

        next_point_ids = self._get_all_next_points(point_to_delete)

        point_position_id, position, output = self.get_position(point_to_delete)

        if point_position_id is None:
            next_points = self._get_all_next_points(point_to_delete)
            if next_points:
                graph[self.GRAPH_ROOT_KEY] = next_points[0]
            else:
                del graph[self.GRAPH_ROOT_KEY]

        elif position == "south":
            graph[point_position_id]["next"][output] = _replace(
                graph[point_position_id]["next"][output],
                point_to_delete.id,
                next_point_ids,
            )
            if not graph[point_position_id]["next"][output]:
                del graph[point_position_id]["next"][output]
            if not graph[point_position_id]["next"]:
                del graph[point_position_id]["next"]
        elif position == "child":
            next_points = self._get_all_next_points(point_to_delete)
            parent_info = graph[point_position_id]
            children_dict = self._get_children_dict(parent_info)
            children_on_edge = children_dict.get(output, [])
            new_children = _replace(children_on_edge, point_to_delete.id, next_points)
            self._set_children(parent_info, output, new_children)

        if not keep_info:
            del graph[str(point_to_delete.id)]

        self._update_graph()

        return GraphPointRemoved(
            point_removed=point_to_delete, dependencies_removed=dependencies
        )

    def replace(self, point_to_replace: GraphPoint, new_point: GraphPoint):
        """
        Replace a point with another at the same position. The new point will take
        the position of the old point, and the old point will be removed from the graph.

        :param point_to_replace: The point to replace.
        :param new_point: The point to replace with.
        """

        self._lock_instance_for_update()

        reference_point_id, position, output = self.get_position(point_to_replace)

        point_to_replace_id = str(point_to_replace.id)
        new_point_id = str(new_point.id)

        self.graph[new_point_id] = self.graph[point_to_replace_id]

        if reference_point_id is None:
            # The replaced point is the root, so the new point becomes the root.
            # (Checked independently of `position` because `get_position` reports the
            # root as `(None, "north", "")`.)
            self.graph[self.GRAPH_ROOT_KEY] = new_point.id
        elif position == "south":
            self.graph[reference_point_id]["next"][output] = _replace(
                self.graph[reference_point_id]["next"][output],
                point_to_replace.id,
                new_point.id,
            )
        elif position == "child":
            parent_info = self.graph[reference_point_id]
            children_dict = self._get_children_dict(parent_info)
            children_on_edge = children_dict.get(output, [])
            new_children = _replace(children_on_edge, point_to_replace.id, new_point.id)
            self._set_children(parent_info, output, new_children)

        del self.graph[point_to_replace_id]

        self._update_graph()

    def move(
        self,
        point_to_move: GraphPoint,
        reference_point: GraphPoint | None,
        position: GraphPointPositionType,
        output: str = "",
        target_graph: Optional["BaseGraphHandler"] = None,
    ):
        """
        Move a point to another position. The point will be removed from its current
        position and inserted at the new position. When `target_graph` is supplied the
        point is removed from this graph and inserted into `target_graph` instead —
        useful for cross-graph moves.

        :param point_to_move: The point to move.
        :param reference_point: The point used as reference for the new position.
            Can be `None` if the point should be moved at the root of the graph.
        :param position: The direction relative to the reference point for the
            new position.
        :param output: The output of the reference point to use for the new position.
        :param target_graph: If provided, insert the point into this graph instead of
            self. Defaults to None (same-graph move).
        """

        # Coerce to a string (the output may be a UUID), treating None as the
        # default "" edge. Without the None guard, str(None) would persist a bogus
        # "None" slot key into the graph (e.g. from a move with a null
        # place_in_container).
        output = "" if output is None else str(output)
        target = target_graph or self
        is_cross_graph = target is not self

        # Moving a point relative to itself would remove it from the graph and
        # then re-insert it relative to its own (now removed) position, leaving
        # a detached "ghost" entry behind. The services guard this too, but the
        # graph is the last line of defense for internal callers.
        if reference_point is not None and reference_point.id == point_to_move.id:
            raise GraphPointReferencePointInvalid(
                f"Point {point_to_move.id} cannot be moved relative to itself."
            )

        # Lock in deterministic (ascending pk) order so two opposite-direction
        # cross-graph moves can never deadlock on each other's row locks.
        self.lock_all_for_update([self, target] if is_cross_graph else [self])

        # A reference inside the moved point's own subtree would loop the
        # subtree back onto its ancestor — a cycle. insert() guards this too,
        # but by then remove() has already spliced the point out; failing here
        # keeps the guard ahead of any graph write. Checked on the source
        # graph, where the subtree lives at this stage of the move.
        if (
            reference_point is not None
            and reference_point.id in self.collect_descendant_ids(point_to_move.id)
        ):
            raise GraphPointReferencePointInvalid(
                f"Point {point_to_move.id} cannot be moved relative to point "
                f"{reference_point.id}, which is inside its own subtree."
            )

        # The reference must be keyed in the graph it will be used in (the
        # target graph for cross-graph moves). insert() re-checks this, but by
        # then remove() has already spliced the point out and persisted;
        # failing here keeps the guard ahead of any graph write.
        if reference_point is not None and str(reference_point.id) not in target.graph:
            raise GraphPointReferencePointInvalid(
                f"Point {point_to_move.id} cannot be moved relative to point "
                f"{reference_point.id}, which is not in the graph."
            )

        # An orphaned point (in the DB but absent from this graph, e.g. created
        # during a not-yet-zero-downtime deployment) has no entry or subtree to
        # capture or remove; the move simply inserts it, making it join the graph.
        point_in_graph = str(point_to_move.id) in self.graph

        descendant_entries = {}
        root_children = None
        if is_cross_graph and point_in_graph:
            # On a cross-graph move the point's whole subtree travels with it, but
            # a plain insert() would create a fresh root entry — dropping the
            # `children` dict — and would leave the descendants' entries behind in
            # the source graph. Capture the subtree before removal so it can be
            # migrated. Note we keep the root's `children` (its descendants) but
            # NOT its `next` (its old siblings, which stay in the source graph);
            # insert() sets the correct `next` for the new position.
            descendant_entries = {
                str(d.id): deepcopy(self.get_info(d))
                for d in self.collect_all_descendants(point_to_move)
            }
            root_children = deepcopy(self.get_info(point_to_move).get("children"))

        self.remove(point_to_move, keep_info=True)

        if is_cross_graph:
            for point_id, entry in descendant_entries.items():
                target.graph[point_id] = entry
            if root_children is not None:
                # Seed the moved point's target entry with only its children, so
                # insert()'s setdefault keeps the subtree intact.
                target.graph[str(point_to_move.id)] = {"children": root_children}

        if reference_point is None and position == GraphPointPosition.SOUTH:
            # null reference + south = "append to end of the chain".
            # insert(None, ...) always places at root (first), so use append() instead.
            target.append(point_to_move)
        else:
            target.insert(point_to_move, reference_point, position, output)

    def remove_isolated_point(self, point: GraphPoint) -> None:
        """
        Remove a point — and all of its graph-reachable descendants — from the
        graph without performing any unlinking.  This is intended for cleaning
        up entries that have already been unlinked (e.g. the stale source-graph
        entries preserved by ``move(keep_info=True)`` for post-move traversal).

        Descendants are collected before the parent entry is removed so that
        the ``children`` dict is still readable during traversal.

        :param point: The point whose graph entry (and descendants) should be
            removed.
        """

        self._lock_instance_for_update()
        for dep in self.collect_all_descendants(point):
            self.graph.pop(str(dep.id), None)
        self.graph.pop(str(point.id), None)
        self._update_graph()

    def _incoming_position(self, point_id: int) -> Optional[GraphPointPositionTriplet]:
        """
        Find where `point_id` is referenced in the live graph, as a
        `(reference_point_id, position, output)` triplet. Unlike
        :meth:`get_position`, this works purely from the serialized graph and an
        integer id — it never resolves the point (or any reference) to a model
        instance — so it is safe to call for a *stale* point whose DB row no longer
        exists.

        :param point_id: The id of the point to locate.
        :return: The incoming position triplet, `(None, "south", "")` if the
            point is the root, or `None` if it isn't referenced anywhere.
        """

        if point_id == self.graph.get(self.GRAPH_ROOT_KEY):
            return None, GraphPointPosition.SOUTH, ""

        for key, info in self.graph.items():
            # Skip the point's own entry (mirroring `get_position`): a corrupted
            # graph can list a point as its own `next` or child, and that
            # self-reference must never be reported as its incoming position.
            if (
                key == self.GRAPH_ROOT_KEY
                or key == str(point_id)
                or not isinstance(info, dict)
            ):
                continue
            for output, next_ids in info.get("next", {}).items():
                if point_id in next_ids:
                    return int(key), GraphPointPosition.SOUTH, output
            for edge, child_ids in self._get_children_dict(info).items():
                if point_id in child_ids:
                    return int(key), GraphPointPosition.CHILD, edge

        return None

    def prune_points(self, ids_to_remove: set[int] | List[int]) -> List[int]:
        """
        Remove "stale" points from the graph: ids still referenced by the
        serialized graph whose underlying model instance no longer exists (e.g. an
        element hard-deleted by older code during a non-zero-downtime deploy). Each
        pruned point is spliced out of its parent's `next` / `children` chain
        and replaced in place by its own default-edge (`next[""]`) successors, so
        surviving siblings stay connected and traversals never reach the missing
        point.

        This operates purely on the serialized graph dict and never resolves a
        point to a model instance — which is exactly why it can run on points whose
        DB row is gone (`remove` cannot, as it traverses real descendants).

        :param ids_to_remove: The point ids to prune.
        :return: The ids that were actually pruned (those present in the graph).
        """

        self._lock_instance_for_update()
        removed: List[int] = []

        for point_id in ids_to_remove:
            point_id = int(point_id)
            point_key = str(point_id)
            if point_key not in self.graph:
                continue

            # The point's default-edge successors take its place in the chain. Its
            # children are intentionally not promoted: a parent is only ever deleted
            # by a cascade that also deletes its children, so those child ids are
            # themselves stale and get pruned (and dropped as detached) in this same
            # pass. A corrupted graph can list the point as its own successor —
            # never splice that back in.
            successors = [
                successor_id
                for successor_id in self.graph[point_key].get("next", {}).get("", [])
                if int(successor_id) != point_id
            ]

            incoming = self._incoming_position(point_id)
            if incoming is None:
                # Already detached (e.g. its parent was pruned earlier in this
                # loop); just drop the leftover entry.
                self.graph.pop(point_key, None)
                removed.append(point_id)
                continue

            reference_id, position, output = incoming
            if reference_id is None:
                # The point is the root: promote its first successor, or empty the
                # graph entirely if it has none.
                if successors:
                    self.graph[self.GRAPH_ROOT_KEY] = successors[0]
                else:
                    self.graph.pop(self.GRAPH_ROOT_KEY, None)
            elif position == GraphPointPosition.SOUTH:
                reference_key = str(reference_id)
                self.graph[reference_key]["next"][output] = _replace(
                    self.graph[reference_key]["next"][output], point_id, successors
                )
                if not self.graph[reference_key]["next"][output]:
                    del self.graph[reference_key]["next"][output]
                if not self.graph[reference_key].get("next"):
                    self.graph[reference_key].pop("next", None)
            else:  # GraphPointPosition.CHILD
                reference_info = self.graph[str(reference_id)]
                children_on_edge = self._get_children_dict(reference_info).get(
                    output, []
                )
                self._set_children(
                    reference_info,
                    output,
                    _replace(children_on_edge, point_id, successors),
                )

            self.graph.pop(point_key, None)
            removed.append(point_id)

        if removed:
            self._update_graph()

        return removed

    @classmethod
    def find_self_referencing_point_ids(cls, graph: SerializedGraph | None) -> set[int]:
        """
        Cheap O(n) scan over the serialized graph for points that reference
        themselves via `next` or `children` — a violation of the graph
        invariant that a point can never be its own successor or child. No
        traversal, no model resolution and no queries, so it is safe to call
        on every request as a fast-path corruption check.

        :param graph: A raw serialized graph dict (maybe `None`).
        :return: The ids of the self-referencing points.
        """

        result: set[int] = set()
        for key, info in (graph or {}).items():
            if key == cls.GRAPH_ROOT_KEY or not isinstance(info, dict):
                continue
            point_id = int(key)
            references = [
                *info.get("next", {}).values(),
                *cls._get_children_dict_from_info(info).values(),
            ]
            if any(point_id in reference_ids for reference_ids in references):
                result.add(point_id)
        return result

    def _remove_references_to(self, target_id: int, from_ids: set[int]):
        """
        Remove every `next`/`children` reference to `target_id` held by the
        points in `from_ids`, cleaning up emptied `next` outputs and children
        edges. Operates purely on the serialized graph; does not persist.

        :param target_id: The id whose incoming references should be removed.
        :param from_ids: The ids of the points to remove the references from.
        """

        for from_id in from_ids:
            info = self.graph.get(str(from_id))
            if not isinstance(info, dict):
                continue

            next_dict = info.get("next", {})
            for output in list(next_dict):
                if target_id in next_dict[output]:
                    remaining = [
                        next_id
                        for next_id in next_dict[output]
                        if int(next_id) != target_id
                    ]
                    if remaining:
                        next_dict[output] = remaining
                    else:
                        del next_dict[output]
            if "next" in info and not info["next"]:
                del info["next"]

            children_dict = self._get_children_dict(info)
            for edge in list(children_dict):
                if target_id in children_dict[edge]:
                    self._set_children(
                        info,
                        edge,
                        [
                            child_id
                            for child_id in children_dict[edge]
                            if int(child_id) != target_id
                        ],
                    )

    def strip_self_references(self) -> List[int]:
        """
        Remove every `next`/`children` reference a point holds to itself. The
        point itself stays in the graph, at the position its parent references;
        only the corrupted self-edges are dropped. The graph is persisted when
        anything was stripped.

        :return: The ids of the points whose self-references were stripped.
        """

        self._lock_instance_for_update()
        stripped = sorted(self.find_self_referencing_point_ids(self.graph))
        for point_id in stripped:
            self._remove_references_to(point_id, {point_id})

        if stripped:
            self._update_graph()

        return stripped

    @classmethod
    def find_dangling_reference_ids(cls, graph: SerializedGraph | None) -> set[int]:
        """
        Return point IDs referenced by ``next`` or ``children`` which have no
        corresponding point entry in the serialized graph.

        :param graph: A raw serialized graph dict (maybe ``None``).
        :return: The IDs referenced by the graph but not keyed in it.
        """

        graph = graph or {}
        point_ids = {int(key) for key in graph if key != cls.GRAPH_ROOT_KEY}
        referenced_ids: set[int] = set()
        for key, info in graph.items():
            if key == cls.GRAPH_ROOT_KEY or not isinstance(info, dict):
                continue
            for next_ids in info.get("next", {}).values():
                referenced_ids.update(int(next_id) for next_id in next_ids)
            for child_ids in cls._get_children_dict_from_info(info).values():
                referenced_ids.update(int(child_id) for child_id in child_ids)

        return referenced_ids - point_ids

    def strip_dangling_references(self) -> List[int]:
        """
        Drop every ``next`` or ``children`` reference whose point has no entry
        in the serialized graph. Valid references on the same edge are kept,
        and empty outputs or child slots are cleaned up.

        :return: The dangling point IDs that were stripped.
        """

        stripped = sorted(self.find_dangling_reference_ids(self.graph))
        from_ids = {int(key) for key in self.graph if key != self.GRAPH_ROOT_KEY}
        for point_id in stripped:
            self._remove_references_to(point_id, from_ids)

        if stripped:
            self._update_graph()

        return stripped

    @classmethod
    def find_cycle_reference_pairs(
        cls, graph: SerializedGraph | None
    ) -> set[tuple[int, int]]:
        """
        Return every `(from_id, target_id)` reference that closes a cycle in
        the graph — a `next`/`children` reference pointing back at a point that
        is already on the traversal path leading to `from_id` (a DFS
        back-edge). A graph containing such a reference makes a point its own
        transitive successor or ancestor, so unguarded walks (e.g. resolving an
        element's ancestry) never terminate.

        The scan is a pure in-memory O(n) iterative depth-first search over the
        serialized graph — no recursion (chains can be deeper than the Python
        recursion limit), no model resolution and no queries — so it is safe to
        call on every request as a fast-path corruption check. The search
        starts from the root so that references on the root-reachable traversal
        tree are never misclassified, then sweeps the remaining (detached)
        points in id order so cycles in detached components are found too.

        Removing every returned reference is guaranteed to leave the graph
        acyclic (every cycle contains at least one back-edge of any DFS
        forest), and never unreaches a point: each back-edge target was already
        reached through the traversal tree before the back-edge was seen.

        :param graph: A raw serialized graph dict (maybe `None`).
        :return: The set of `(from_id, target_id)` cycle-closing references.
        """

        graph = graph or {}

        def outgoing(point_id: int) -> List[int]:
            info = graph.get(str(point_id))
            if not isinstance(info, dict):
                return []
            refs: List[int] = []
            for next_ids in info.get("next", {}).values():
                refs.extend(int(next_id) for next_id in next_ids)
            for child_ids in cls._get_children_dict_from_info(info).values():
                refs.extend(int(child_id) for child_id in child_ids)
            # A dangling reference has no entry to traverse into, so it can
            # never close a cycle; `strip_dangling_references` owns those.
            return [ref for ref in refs if str(ref) in graph]

        back_edges: set[tuple[int, int]] = set()
        on_path: set[int] = set()
        done: set[int] = set()

        start_ids: List[int] = []
        if cls.GRAPH_ROOT_KEY in graph and str(graph[cls.GRAPH_ROOT_KEY]) in graph:
            start_ids.append(int(graph[cls.GRAPH_ROOT_KEY]))
        start_ids.extend(sorted(int(key) for key in graph if key != cls.GRAPH_ROOT_KEY))

        for start_id in start_ids:
            if start_id in done:
                continue
            on_path.add(start_id)
            stack = [(start_id, iter(outgoing(start_id)))]
            while stack:
                point_id, refs_iterator = stack[-1]
                pushed = False
                for ref in refs_iterator:
                    if ref in on_path:
                        back_edges.add((point_id, ref))
                    elif ref not in done:
                        on_path.add(ref)
                        stack.append((ref, iter(outgoing(ref))))
                        pushed = True
                        break
                if not pushed:
                    stack.pop()
                    on_path.discard(point_id)
                    done.add(point_id)

        return back_edges

    def strip_cycle_references(self) -> List[tuple[int, int]]:
        """
        Remove every cycle-closing `next`/`children` reference from the graph
        (see `find_cycle_reference_pairs`). Only the corrupted back-edges are
        dropped: every point stays in the graph at the position its traversal
        tree reaches it, so the repair is minimal and never detaches a
        root-reachable point. The graph is persisted when anything was
        stripped.

        :return: The `(from_id, target_id)` pairs that were stripped.
        """

        self._lock_instance_for_update()
        stripped = sorted(self.find_cycle_reference_pairs(self.graph))
        for from_id, target_id in stripped:
            self._remove_references_to(target_id, {from_id})

        if stripped:
            self._update_graph()

        return stripped

    @classmethod
    def find_converging_reference_pairs(
        cls, graph: SerializedGraph | None
    ) -> set[tuple[int, int]]:
        """
        Return every `(from_id, target_id)` reference that gives a point more
        than one incoming reference. The graph invariant is that every point
        has exactly one incoming position (the previous-position map and
        `get_position` are single-valued), so converging references — two
        chains "merging" onto one point — are corruption: splices resolve only
        one of the predecessors, letting the other survive and compound (this
        is the aftermath left behind by pre-guard double inserts).

        For each converging point one canonical reference is kept and the rest
        are returned for stripping:

        - the root pointer always wins (it cannot be stripped);
        - otherwise the reference whose source is discovered first by a
          breadth-first walk from the root, so the kept reference is on the
          root-reachable traversal and stripping never unreaches the point;
        - for points only referenced from detached components, the lowest
          source id wins, deterministically;
        - a source holding several references to the same point contributes
          all of them (reference removal is per source-target pair), so it is
          only eligible as canonical when it references the point exactly
          once. When no eligible source remains every reference is returned;
          the detached point is then re-attached by
          `reattach_unreachable_points`.

        Self-references are never canonical and never returned — they are
        `find_self_referencing_point_ids`' responsibility. References to
        unkeyed points are ignored too (`strip_dangling_references` owns
        those). A pure in-memory O(n) scan: no recursion, no model resolution,
        no queries.

        :param graph: A raw serialized graph dict (maybe `None`).
        :return: The set of `(from_id, target_id)` surplus references.
        """

        graph = graph or {}

        def refs_of(point_id: int) -> List[int]:
            info = graph.get(str(point_id))
            if not isinstance(info, dict):
                return []
            refs: List[int] = []
            for next_ids in info.get("next", {}).values():
                refs.extend(int(next_id) for next_id in next_ids)
            for child_ids in cls._get_children_dict_from_info(info).values():
                refs.extend(int(child_id) for child_id in child_ids)
            return refs

        # Collect every incoming reference per keyed target (with
        # multiplicity), excluding self-references.
        root_id = graph.get(cls.GRAPH_ROOT_KEY)
        incoming: Dict[int, List[int]] = {}
        for key in graph:
            if key == cls.GRAPH_ROOT_KEY:
                continue
            source_id = int(key)
            for target_id in refs_of(source_id):
                if target_id == source_id or str(target_id) not in graph:
                    continue
                incoming.setdefault(target_id, []).append(source_id)

        converging = {
            target_id: source_ids
            for target_id, source_ids in incoming.items()
            if len(source_ids) + (1 if target_id == root_id else 0) > 1
        }
        if not converging:
            return set()

        # Breadth-first discovery order from the root, to prefer canonical
        # references that sit on the root-reachable traversal.
        discovery_index: Dict[int, int] = {}
        if root_id is not None and str(root_id) in graph:
            queue = [int(root_id)]
            while queue:
                current = queue.pop(0)
                if current in discovery_index:
                    continue
                discovery_index[current] = len(discovery_index)
                queue.extend(ref for ref in refs_of(current) if str(ref) in graph)

        pairs: set[tuple[int, int]] = set()
        for target_id, source_ids in converging.items():
            if target_id == root_id:
                # The root pointer is the canonical reference; every real
                # reference to the root point is surplus.
                pairs.update((source_id, target_id) for source_id in source_ids)
                continue

            counts: Dict[int, int] = {}
            for source_id in source_ids:
                counts[source_id] = counts.get(source_id, 0) + 1
            eligible = [source_id for source_id, count in counts.items() if count == 1]
            canonical = min(
                eligible,
                key=lambda source_id: (
                    source_id not in discovery_index,
                    discovery_index.get(source_id, 0),
                    source_id,
                ),
                default=None,
            )
            pairs.update(
                (source_id, target_id) for source_id in counts if source_id != canonical
            )

        return pairs

    def strip_converging_references(self) -> List[tuple[int, int]]:
        """
        Remove every surplus incoming reference from the graph (see
        `find_converging_reference_pairs`), so that each point is left with a
        single canonical incoming position. Stripping can detach a subtree
        whose only surviving path ran through a stripped reference; callers
        follow up with `reattach_unreachable_points` (as the builder heal
        does). The graph is persisted when anything was stripped.

        :return: The `(from_id, target_id)` pairs that were stripped.
        """

        self._lock_instance_for_update()
        stripped = sorted(self.find_converging_reference_pairs(self.graph))
        for from_id, target_id in stripped:
            self._remove_references_to(target_id, {from_id})

        if stripped:
            self._update_graph()

        return stripped

    def strip_children_edges(self, point: GraphPoint, edges: List[str]) -> List[int]:
        """
        Remove the given children edges from a point's entry. The referenced
        subtrees keep their own entries and simply become unreachable — the
        caller is expected to follow up with `reattach_unreachable_points`
        (as the builder heal does). Used to repair children stored under an
        edge the point cannot have (e.g. a non-container that gained children
        through corruption). The graph is persisted when anything was dropped.

        :param point: The point whose children edges should be removed.
        :param edges: The edge keys to drop.
        :return: The ids that were directly referenced by the dropped edges.
        """

        self._lock_instance_for_update()
        info = self.get_info(point)
        children_dict = self._get_children_dict(info)
        dropped: List[int] = []
        for edge in edges:
            if edge in children_dict:
                dropped.extend(int(child_id) for child_id in children_dict[edge])
                self._set_children(info, edge, [])

        if dropped:
            self._update_graph()

        return dropped

    @classmethod
    def find_unreachable_point_ids(cls, graph: SerializedGraph | None) -> set[int]:
        """
        Return the ids of every point keyed in the graph that cannot be reached
        from the root by following `next` (all outputs) and `children` (all
        edges). Detached points are invisible to ordered traversals and cannot
        be positioned (`get_position` raises), so they need re-attaching.

        A pure in-memory O(n) walk with a seen set — no model resolution and no
        queries — so it is safe to call on every request as a fast-path
        corruption check.

        :param graph: A raw serialized graph dict (maybe `None`).
        :return: The ids of the unreachable points.
        """

        graph = graph or {}
        all_ids = {int(key) for key in graph if key != cls.GRAPH_ROOT_KEY}

        reachable: set[int] = set()
        stack = [int(graph[cls.GRAPH_ROOT_KEY])] if cls.GRAPH_ROOT_KEY in graph else []
        while stack:
            point_id = stack.pop()
            if point_id in reachable:
                continue
            reachable.add(point_id)

            info = graph.get(str(point_id))
            if not isinstance(info, dict):
                continue
            for next_ids in info.get("next", {}).values():
                stack.extend(int(next_id) for next_id in next_ids)
            for child_ids in cls._get_children_dict_from_info(info).values():
                stack.extend(int(child_id) for child_id in child_ids)

        return all_ids - reachable

    def reattach_unreachable_points(
        self,
        container: GraphPoint | None = None,
        slot: str = "",
    ) -> List[int]:
        """
        Re-attach every unreachable point at the bottom of the graph, so it
        becomes the last point of the default chain (visible and deletable
        again). Only the *head* of each detached subtree is linked; its chain
        and children ride along untouched. The graph is persisted when
        anything was re-attached.

        :param container: When given, attach at the end of this container's
            `slot` children chain instead of the end of the root chain (e.g.
            the shared page's root container).
        :param slot: The children edge of `container` to attach into.
        :return: The ids of the re-attached (head) points.
        """

        self._lock_instance_for_update()

        def attach(head_id: int):
            if container is not None:
                container_info = self.get_info(container)
                head_ids = self._get_children_dict(container_info).get(slot, [])
                if head_ids:
                    tail_key = self._get_chain_tail_id(head_ids[0])
                    self.graph.setdefault(tail_key, {}).setdefault("next", {})[""] = [
                        head_id
                    ]
                else:
                    self._set_children(container_info, slot, [head_id])
            elif self.GRAPH_ROOT_KEY not in self.graph:
                self.graph[self.GRAPH_ROOT_KEY] = head_id
            else:
                tail_key = self._get_chain_tail_id(self.graph[self.GRAPH_ROOT_KEY])
                self.graph.setdefault(tail_key, {}).setdefault("next", {})[""] = [
                    head_id
                ]

        reattached: List[int] = []
        while unreachable := self.find_unreachable_point_ids(self.graph):
            # Heads are unreachable points that no other unreachable point
            # references — attaching a head brings its whole subtree back.
            referenced: set[int] = set()
            for point_id in unreachable:
                info = self.graph.get(str(point_id))
                if not isinstance(info, dict):
                    continue
                for next_ids in info.get("next", {}).values():
                    referenced.update(int(next_id) for next_id in next_ids)
                for child_ids in self._get_children_dict(info).values():
                    referenced.update(int(child_id) for child_id in child_ids)

            heads = sorted(unreachable - referenced)
            if not heads:
                # A fully cyclic detached component (e.g. A -> B -> A with no
                # external reference): break the cycle deterministically at the
                # lowest id so it gains a head, then re-attach it.
                head = min(unreachable)
                self._remove_references_to(head, unreachable)
                heads = [head]

            for head in heads:
                attach(head)
                reattached.append(head)

        if reattached:
            self._update_graph()

        return reattached

    def migrate_graph(self, id_mapping: Dict[str, Any]):
        """
        Updates the point IDs and edge UIDs in the graph from the id_mapping.

        A corrupted source graph can reference points that have no imported
        counterpart in the id_mapping (e.g. an exported graph carrying a stale
        reference to a record that no longer existed at export time). Keyed
        entries for such points are pruned first — splicing their mapped
        successors into place so surviving chains stay connected — and
        remaining unkeyed dangling references are dropped during mapping, so a
        corrupted export can always be imported.

        :param id_mapping: A dict containing the mapping of old IDs to new IDs for both
            points and edges.
        """

        self._lock_instance_for_update()

        # The mapping key is absent when nothing was imported for this graph's
        # point model (e.g. a page with no elements): every graph reference is
        # then unmapped by definition.
        point_mapping = id_mapping.get(self.instance_id_mapping, {})

        stale_ids = {
            int(key) for key in self.graph if key != self.GRAPH_ROOT_KEY
        } - set(point_mapping)
        if stale_ids:
            self.prune_points(stale_ids)

        migrated = {}

        def is_mapped(nid):
            return int(nid) in point_mapping

        def map_point(nid):
            return point_mapping[int(nid)]

        def map_output(uid):
            if uid == "":
                return ""
            return id_mapping[self.outputs_id_mapping][uid]

        for key, info in self.graph.items():
            if key == self.GRAPH_ROOT_KEY:
                # An unmapped root reference (an unkeyed dangling id) is
                # dropped; a keyed stale root was already promoted by the
                # prune above.
                if is_mapped(info):
                    migrated[self.GRAPH_ROOT_KEY] = map_point(info)

            else:
                migrated[str(map_point(key))] = {}
                if "next" in info:
                    migrated[str(map_point(key))]["next"] = {
                        map_output(uid): [
                            map_point(nid) for nid in nids if is_mapped(nid)
                        ]
                        for uid, nids in info["next"].items()
                    }
                if "children" in info:
                    children = info["children"]
                    if isinstance(children, list):
                        # Legacy format: migrate to new dict format with default edge
                        migrated[str(map_point(key))]["children"] = {
                            "": [map_point(nid) for nid in children if is_mapped(nid)]
                        }
                    else:
                        # New format: children edge keys are place names (e.g. "0",
                        # "1") that are static and don't need remapping — only `next`
                        # edge keys are output UIDs that need remapping.
                        migrated[str(map_point(key))]["children"] = {
                            edge_key: [map_point(nid) for nid in nids if is_mapped(nid)]
                            for edge_key, nids in children.items()
                        }

        self._update_graph(migrated)

    def labeled_graph(self):
        """
        Generate a graph representation that doesn't depend on the point IDs and that is
        reliable between test executions.
        """

        used_label = {}

        def get_label(point_id) -> str:
            point_id = str(point_id)
            label = self.get_point(point_id).graph_point_label

            while used_label.setdefault(label, point_id) != point_id:
                label += "-"

            return label

        result = {}
        for key, point_info in self.graph.items():
            if key == self.GRAPH_ROOT_KEY:
                result[key] = get_label(point_info)
            else:
                result[get_label(key)] = {}
                if "children" in point_info:
                    children_dict = self._get_children_dict(point_info)
                    result[get_label(key)]["children"] = {
                        self.get_point(key).graph_point_edge_label(edge_key): [
                            get_label(child_id) for child_id in child_ids
                        ]
                        for edge_key, child_ids in children_dict.items()
                    }
                if "next" in point_info:
                    result[get_label(key)]["next"] = {
                        self.get_point(key).graph_point_edge_label(o): [
                            get_label(point_id) for point_id in n
                        ]
                        for o, n in point_info["next"].items()
                    }

        return result
