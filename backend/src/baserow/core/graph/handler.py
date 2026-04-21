from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from baserow.core.graph.exceptions import (
    GraphPointDoesNotExist,
    GraphPointNotFoundInGraph,
)
from baserow.core.graph.types import (
    GraphModelInstance,
    GraphPoint,
    GraphPointPositionTriplet,
    GraphPointPositionType,
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


class GraphMode(Enum):
    GRAPH_ID = "GRAPH_ID"
    GRAPH_POINT = "GRAPH_POINT"


class BaseGraphHandler(ABC):
    """
    The base handler to support all automation workflow and application builder graph
    operations. Most operation over the graph structure should happen here.

    The structure looks like:

    ```
    {
        "0": 1,
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

    outputs_id_mapping: str = ""
    instance_id_mapping: str = ""
    does_not_exist_exception = GraphPointDoesNotExist
    base_point_class: Type["GraphPointMixin"] = None

    def __init__(
        self, instance: GraphModelInstance, mode: GraphMode = GraphMode.GRAPH_POINT
    ):
        self.instance = instance
        self.mode = mode

    @property
    def graph(self) -> SerializedGraph:
        return self.instance.graph

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

    @staticmethod
    def get_order_map(graph: SerializedGraph) -> Dict[int, Decimal]:
        """
        Returns a mapping of point_id to order Decimal for all points in the graph.

        Root-level points are ordered by their position in the `next[""]` chain
        starting from graph["0"]. Children in each place are ordered by their
        position in the `next[""]` chain starting from the first child in that place
        — including points reachable only via `next`, not just those listed
        explicitly in `children`.

        :param graph: The serialized graph to compute orders from.
        :return: A dict mapping each point ID (int) to its Decimal order.
        """

        orders = {}

        def _follow_chain(start_id):
            current = start_id
            i = 1
            while current is not None:
                orders[int(current)] = Decimal(f"{i}.{'0' * 20}")
                point_next = graph.get(str(current), {}).get("next", {})
                # Each non-default branch starts its own chain at order 1
                for output, next_ids in point_next.items():
                    if output != "" and next_ids:
                        _follow_chain(next_ids[0])
                next_ids = point_next.get("", [])
                current = next_ids[0] if next_ids else None
                i += 1

        # Root-level points: follow next chain from graph["0"]
        if "0" in graph:
            _follow_chain(graph["0"])

        # Children: for each place, follow next chain from the first child
        for point_id, info in graph.items():
            if point_id == "0" or not isinstance(info, dict):
                continue
            children = info.get("children", {})
            if isinstance(children, list):
                children = {"": children}
            for child_ids in children.values():
                if child_ids:
                    _follow_chain(child_ids[0])

        return orders

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
            point_id = self.graph["0"]

        elif hasattr(point, "id"):
            point_id = point.id
        else:
            point_id = point

        return self.graph[str(point_id)]

    def _get_children_dict(
        self, point_info: Dict[str, Any]
    ) -> Dict[str, List[int | str]]:
        """
        Get the children as a dict, normalizing from the legacy array format if needed.

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

        output = str(output)

        if position == "south":
            # First point
            if reference_point is None:
                if "0" in self.graph:
                    return self.get_point(self.graph["0"])
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

        if self.graph.get("0") is None:
            return None, "south", ""

        def search_last(point_id):
            next_points = self.get_info(point_id).get("next", {}).get("", [])
            if not next_points:
                return self.get_point(point_id), "south", ""
            else:
                return search_last(next_points[0])

        return search_last(self.graph["0"])

    def append(self, point: GraphPoint) -> None:
        """
        Insert a point at the end of the default edge chain.
        """

        ref, position, output = self.get_last_position()
        self.insert(point, ref, position, output)

    def get_position(self, point: GraphPoint) -> GraphPointPositionTriplet:
        """
        Return the position of the given point in the graph as a triplet of
        `[reference_point, position, output]`.

        :param point: The point to get the position from.
        :return: A triplet of `[reference_point, position, output]` describing the
            position of the given point in the graph. If the point is the root point,
            it will return `(None, "south", "")`.
        :raises GraphPointNotFoundInGraph: If the point is not found in the graph.
        """

        # Is it the root point?
        if point.id == self.graph.get("0", None):
            return None, "south", ""

        for point_id, point_info in self.graph.items():
            if point_id == "0" or point_id == str(point.id):
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
    ) -> GraphPointPositionTriplet | None:
        """
        Given a `GraphPoint`, generates the list of all positions to get to the
        target `GraphPoint`. The positions are represented as a list of triplets of
        `[reference_point, position, output]`.

        :param target_point: The point to get the positions to.
        :return: A list of triplets of `[reference_point, position, output]` describing
            the positions to get to the target point. If the target point is not found
            in the graph, it will return `None`.
        """

        def explore(current_position: GraphPoint, path):
            point = self.get_point_at_position(*current_position)

            point_id = str(point.id)

            if point_id == str(target_point.id):
                return path

            point_info = self.get_info(point_id)

            next_positions = []
            # Collect all possible positions
            next_positions.extend(
                [
                    (point_id, "south", uid)
                    for uid, points in point_info.get("next", {}).items()
                    if points
                ]
            )
            children_dict = self._get_children_dict(point_info)
            next_positions.extend(
                [
                    (point_id, "child", edge_key)
                    for edge_key, children in children_dict.items()
                    if children
                ]
            )

            for next_position in next_positions:
                found = explore(next_position, path + [next_position])
                if found is not None:
                    return found

            return None

        full_path = explore((None, "south", ""), [])
        if full_path is not None:
            return [(self.get_point(nid), p, o) for [nid, p, o] in full_path]

        return None

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

        point_info = self.get_info(point)
        children_dict = self._get_children_dict(point_info)
        result = []
        for edge_key, child_ids in children_dict.items():
            if output is not None and edge_key != output:
                continue
            for cid in child_ids:
                if first_only:
                    result.append(self.get_point(cid))
                else:
                    result.extend(self._get_chain_elements(cid))
        return result

    @classmethod
    def generate_parent_map_cache_key(cls, graph_model_id: int) -> str:
        return f"parent_map_{graph_model_id}"

    @staticmethod
    def build_parent_map(graph: SerializedGraph | None) -> Dict[int, int]:
        """
        Build and return a mapping of `{child_id: parent_id}` for all points
        that are direct children (or chained via `next[""]`) of a container,
        given a raw graph dict.

        This static method is the canonical implementation; the instance method
        `get_parent_map` delegates to it with `self.graph`.

        :param graph: A raw serialized graph dict (maybe `None`).
        :return: A dict mapping each child point ID (int) to its parent
            point ID (int).
        """

        parent_map: Dict[int, int] = {}
        for str_id, info in (graph or {}).items():
            if str_id == "0" or not isinstance(info, dict):
                continue
            node_id = int(str_id)

            # Inline _get_children_dict logic so this can be a static method.
            children = info.get("children")
            if children is None:
                children_dict = {}
            elif isinstance(children, list):
                children_dict = {"": children} if children else {}
            else:
                children_dict = children

            for child_ids in children_dict.values():
                for chain_head in child_ids:
                    current_id = chain_head
                    while current_id is not None:
                        parent_map[int(current_id)] = node_id
                        child_info = (graph or {}).get(str(current_id), {})
                        next_ids = child_info.get("next", {}).get("", [])
                        current_id = next_ids[0] if next_ids else None
        return parent_map

    def get_parent_map(self) -> Dict[int, int]:
        """
        Build and return a mapping of `{child_id: parent_id}` for all points
        that are direct children (or chained via `next[""]`) of a container.

        Walks the `next[""]` chains within each children place so that all
        points in a chain share the same parent container.

        :return: A dict mapping each child point ID (int) to its parent
            point ID (int).
        """

        return self.build_parent_map(self.graph)

    def _get_chain_tail_id(self, first_id: str | int) -> str:
        """
        Follow the default next[""] chain from first_id and return the string ID of
        the last element — the one that has no next[""] successor.

        :param first_id: The starting point ID.
        :return: String ID of the tail element.
        """

        current = str(first_id)
        while True:
            next_ids = self.graph.get(current, {}).get("next", {}).get("", [])
            if not next_ids:
                return current
            current = str(next_ids[0])

    def _get_chain_elements(self, first_id: str | int) -> List[GraphPoint] | List[int]:
        """
        Collect all graph points reachable via the default next[""] chain from
        first_id, in order.

        Returns model instances in GRAPH_POINT mode, or integer IDs in GRAPH_ID mode.

        :param first_id: The starting point ID.
        :return: Ordered list of all points (or IDs) in the chain.
        """

        result = []
        current = str(first_id)
        while current:
            if self.mode == GraphMode.GRAPH_ID:
                result.append(int(current))
            else:
                result.append(self.get_point(int(current)))
            next_ids = self.graph.get(current, {}).get("next", {}).get("", [])
            current = str(next_ids[0]) if next_ids else None
        return result

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

        output = str(output)  # When it's a UUID

        graph = self.graph
        point_info = graph.setdefault(str(point.id), {})
        new_next = None

        # If the `reference_point` is `None`, it means that we want to insert the
        # point at the root of the graph. In this case, we need to update the root
        # of the graph to point to the new point, and make the old root (if it exists)
        # a child of the new point.
        if reference_point is None:
            if "0" in graph:
                new_next = [graph["0"]]

            # Our `point` is now the root of the graph.
            graph["0"] = point.id

            if new_next:
                point_info["next"] = {"": new_next}

            self._update_graph()
            return

        if position == "north":
            # Insert the point before the reference point. The new point takes
            # the reference point's position, and the reference point becomes
            # the new point's next on the default output.
            ref_position_id, ref_position, ref_output = self.get_position(
                reference_point
            )

            # If the reference itself has no reference ID, then it's the root.
            # We'll then replace the root with our new `point`.
            if ref_position_id is None:
                graph["0"] = point.id
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

        if position == "south":
            if output in self.get_info(reference_point).get("next", {}):
                new_next = self.get_info(reference_point)["next"][output]

            self.get_info(reference_point).setdefault("next", {})[output] = [point.id]

        elif position == "child":
            ref_info = self.get_info(reference_point)
            children_dict = self._get_children_dict(ref_info)

            if output in children_dict:
                # Follow the next[""] chain from the first child to find the
                # last element in the chain, then append the new point there.
                current_id = children_dict[output][0]
                while True:
                    next_ids = self.get_info(current_id).get("next", {}).get("", [])
                    if not next_ids:
                        break
                    current_id = next_ids[0]
                self.get_info(current_id).setdefault("next", {})[""] = [point.id]
            else:
                # No children yet in this slot — set as the first child.
                self._set_children(ref_info, output, [point.id])

        if new_next:
            point_info["next"] = {"": new_next}
        else:
            if "next" in point_info:
                del point_info["next"]

        self._update_graph()

    def remove(self, point_to_delete: GraphPoint, keep_info: bool = False):
        """
        Remove the given point.

        :param point_to_delete: The point to delete.
        :param keep_info: doesn't delete the info dict from the graph yet if True.
        """

        graph = self.instance.graph

        if str(point_to_delete.id) not in graph:
            # The point is already removed. Could be by a replacement.
            return

        next_point_ids = self._get_all_next_points(point_to_delete)

        point_position_id, position, output = self.get_position(point_to_delete)

        if point_position_id is None:
            next_points = self._get_all_next_points(point_to_delete)
            if next_points:
                graph["0"] = next_points[0]
            else:
                del graph["0"]

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

    def replace(self, point_to_replace: GraphPoint, new_point: GraphPoint):
        """
        Replace a point with another at the same position. The new point will take
        the position of the old point, and the old point will be removed from the graph.

        :param point_to_replace: The point to replace.
        :param new_point: The point to replace with.
        """

        reference_point_id, position, output = self.get_position(point_to_replace)

        point_to_replace_id = str(point_to_replace.id)
        new_point_id = str(new_point.id)

        self.graph[new_point_id] = self.graph[point_to_replace_id]

        if position == "south":
            if reference_point_id is None:
                self.graph["0"] = new_point.id
            else:
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
    ):
        """
        Move a point to another position. The point will be removed from its current
        position and inserted at the new position.

        :param point_to_move: The point to move.
        :param reference_point: The point used as reference for the new position.
            Can be `None` if the point should be moved at the root of the graph.
        :param position: The direction relative to the reference point for the
            new position.
        :param output: The output of the reference point to use for the new position.
        """

        output = str(output)  # When it's a UUID
        self.remove(point_to_move, keep_info=True)
        self.insert(point_to_move, reference_point, position, output)

    def migrate_graph(self, id_mapping: Dict[str, Any]):
        """
        Updates the point IDs and edge UIDs in the graph from the id_mapping.

        :param id_mapping: A dict containing the mapping of old IDs to new IDs for both
            points and edges.
        """

        migrated = {}

        def map_point(nid):
            return id_mapping[self.instance_id_mapping][int(nid)]

        def map_output(uid):
            if uid == "":
                return ""
            return id_mapping[self.outputs_id_mapping][uid]

        for key, info in self.graph.items():
            if key == "0":
                migrated["0"] = id_mapping[self.instance_id_mapping][info]

            else:
                migrated[str(map_point(key))] = {}
                if "next" in info:
                    migrated[str(map_point(key))]["next"] = {
                        map_output(uid): [map_point(nid) for nid in nids]
                        for uid, nids in info["next"].items()
                    }
                if "children" in info:
                    children = info["children"]
                    if isinstance(children, list):
                        # Legacy format: migrate to new dict format with default edge
                        migrated[str(map_point(key))]["children"] = {
                            "": [map_point(nid) for nid in children]
                        }
                    else:
                        # New format: children edge keys are place names (e.g. "0",
                        # "1") that are static and don't need remapping — only `next`
                        # edge keys are output UIDs that need remapping.
                        migrated[str(map_point(key))]["children"] = {
                            edge_key: [map_point(nid) for nid in nids]
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
            if key == "0":
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
