from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

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
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {
            "next": {
                "uuid1": [3],
                "uui2": [5],
                "": [4],
            }
        },
        "3": {},
        "5": {},
        "4": {"next": {"": [6]}},
        "6": {"children": [7]}
        "7": {}
    }
    ```

    The key is the ID of a point, except for the key '0' that indicates the ID of the
    first point of the graph.

    For each point, `next` is the dict keyed by edge UUIDs and valued by the list of
    point ID on this edge. For now only one point is possible per output.

    `children` is an array of children for the points which support children.

    This graph structure use triplet of position to identify the position of a point.
    A triplet looks like [reference_point, position, output].

    For instance:
    - [<Point(42)>, 'south', ''] refers to the point placed at the
    south of the point 42 at default output "".
    - [<Point(42)>, 'south', 'uuid45'] refers to the point placed at the
    south of the point 42 at the edge with uid `uuid45`.
    - [<Point(42)>, 'child', ''] refers to the point placed as child of the
    point 42.
    """

    outputs_id_mapping: str = ""
    instance_id_mapping: str = ""
    does_not_exist_exception = GraphPointDoesNotExist

    def __init__(self, instance: GraphModelInstance):
        self.instance = instance

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
            children = self.get_info(reference_point).get("children", [])
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

            if point.id in point_info.get("children", []):
                return point_id, "child", ""

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
            if point_info.get("children"):
                next_positions.append((point_id, "child", ""))

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

    def get_children(self, point: GraphPoint) -> List[GraphPoint]:
        """
        Get the children of the given point.

        :param point: The point to get the children from.
        :return: A list of children of the given point.
        """

        return [self.get_point(cid) for cid in self.get_info(point).get("children", [])]

    def get_siblings(self, point: GraphPoint) -> List[GraphPoint]:
        """
        Get the siblings of the given point. Siblings are points that share the same
        parent.

        :param point: The point to get the siblings from.
        :return: A list of siblings of the given point.
        """

        # Only consider it a "sibling" relationship if this point is a child
        parent_point_id, position, output = self.get_position(point)
        if position != "child":
            return []

        return [
            self.get_point(pid)
            for pid in self.get_info(parent_point_id).get("children", [])
            if pid != point.id
        ]

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
                self.get_info(ref_position_id)["children"] = _replace(
                    self.get_info(ref_position_id)["children"],
                    reference_point.id,
                    point.id,
                )

            point_info["next"] = {"": [reference_point.id]}

            self._update_graph()
            return

        if position == "south":
            if output in self.get_info(reference_point).get("next", {}):
                new_next = self.get_info(reference_point)["next"][output]

            self.get_info(reference_point).setdefault("next", {})[output] = [point.id]

        elif position == "child":
            if "children" in self.get_info(reference_point):
                new_next = self.get_info(reference_point)["children"]

            self.get_info(reference_point)["children"] = [point.id]

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
            graph[point_position_id]["children"] = _replace(
                graph[point_position_id]["children"],
                point_to_delete.id,
                next_points,
            )
            if not graph[point_position_id]["children"]:
                del graph[point_position_id]["children"]

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
            self.graph[reference_point_id]["children"] = _replace(
                self.graph[reference_point_id]["children"],
                point_to_replace.id,
                new_point.id,
            )

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
                    migrated[str(map_point(key))]["children"] = [
                        map_point(nid) for nid in info["children"]
                    ]

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
                label += f"-{point_id}"

            return label

        result = {}
        for key, point_info in self.graph.items():
            if key == "0":
                result[key] = get_label(point_info)
            else:
                result[get_label(key)] = {}
                if "children" in point_info:
                    result[get_label(key)]["children"] = [
                        get_label(id) for id in point_info["children"]
                    ]
                if "next" in point_info:
                    result[get_label(key)]["next"] = {
                        self.get_point(key).graph_point_edge_label(o): [
                            get_label(id) for id in n
                        ]
                        for o, n in point_info["next"].items()
                    }

        return result
