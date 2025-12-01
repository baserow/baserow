from typing import Any, Dict, List

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeNotFoundInGraph,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.types import NodePositionTriplet, NodePositionType


def _replace(list_, item_to_replace, replacement):
    index = list_.index(item_to_replace)

    return (
        list_[:index]
        + (replacement if isinstance(replacement, list) else [replacement])
        + list_[index + 1 :]
    )


class NodeGraphHandler:
    """
    Handler to support all workflow node graph operation. Most operation over the graph
    structure should happen here.

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

    The key is the ID of a node except for the key '0' that indicates the ID of the
    first node of the graph.

    For each node, `next` is the dict keyed by edge UUIDs and valued by the list of
    node ID on this edge. For now only one node is possible per output.

    `children` is an array of children for the container node.

    This graph structure use triplet of position to identify the position of a node.
    A triplet looks like [reference_node, position, output].

    For instance:
    - [<AutomationNode(42)>, 'south', ''] refers to the node placed at the
    south of the node 42 at default output "".
    - [<AutomationNode(42)>, 'south', 'uuid45'] refers to the node placed at the
    south of the node 42 at the edge with uid `uuid45`.
    - [<AutomationNode(42)>, 'child', ''] refers to the node placed as child of the
    node 42.
    """

    def __init__(self, workflow):
        self.workflow = workflow

    @property
    def graph(self):
        return self.workflow.graph

    def _update_graph(self, graph=None):
        """
        Save the workflow graph.
        """

        if graph is not None:
            self.workflow.graph = graph

        self.workflow.save(update_fields=["graph"])

    def get_info(self, node: AutomationNode | str | int | None) -> Dict[str, Any]:
        """
        Returns the info dict for the given node.
        """

        if node is None:
            node_id = self.graph["0"]

        elif hasattr(node, "id"):
            node_id = node.id
        else:
            node_id = node

        return self.graph[str(node_id)]

    def _get_node_map(self) -> Dict[int, AutomationNode]:
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        return {n.id: n for n in AutomationNodeHandler().get_nodes(self.workflow)}

    def get_node(self, node_id: str | int) -> AutomationNode:
        """
        Return the node instance for the given node ID.
        """

        if int(node_id) not in self._get_node_map():
            raise AutomationNodeDoesNotExist(node_id)

        return self._get_node_map()[int(node_id)]

    def get_node_at_position(
        self, reference_node: AutomationNode, position: NodePositionType, output: str
    ) -> AutomationNode:
        """
        Returns the node at the given position in the graph.

        :param reference_node: The node used as reference for the position.
        :param position: The direction relative to the reference node.
        :param output: The output of the reference node to use.
        """

        output = str(output)

        if position == "south":
            # First node
            if reference_node is None:
                if "0" in self.graph:
                    return self.get_node(self.graph["0"])
                else:
                    return None

            next_nodes = self.get_info(reference_node).get("next", {}).get(output, [])
            if next_nodes:
                return self.get_node(next_nodes[0])

        elif position == "child":
            children = self.get_info(reference_node).get("children", [])
            if children:
                return self.get_node(children[0])

        return None

    def get_last_position(self) -> NodePositionTriplet:
        """
        Return the last position of the graph if we follow the default edge ("") of
        each node. Mostly used to place nodes in tests.
        """

        if self.graph.get("0") is None:
            return (None, "south", "")

        def search_last(node_id):
            next_nodes = self.get_info(node_id).get("next", {}).get("", [])
            if not next_nodes:
                return (self.get_node(node_id), "south", "")
            else:
                return search_last(next_nodes[0])

        return search_last(self.graph["0"])

    def get_position(self, node: AutomationNode) -> NodePositionTriplet:
        """
        Returns the position of the given node.
        """

        if node.id == self.graph.get("0", None):
            # it's the trigger
            return (None, "south", "")

        for node_id, node_info in self.graph.items():
            if node_id == "0" or node_id == str(node.id):
                continue

            for output_uid, next_nodes in node_info.get("next", {}).items():
                if node.id in next_nodes:
                    return (node_id, "south", output_uid)

            if node.id in node_info.get("children", []):
                return (node_id, "child", "")

        raise AutomationNodeNotFoundInGraph(f"Node {node.id} not found in the graph")

    def get_previous_positions(
        self, target_node: AutomationNode
    ) -> NodePositionTriplet:
        """
        Generates the list of all positions to get to the target node.
        """

        def explore(current_position, path):
            node = self.get_node_at_position(*current_position)

            node_id = str(node.id)

            if node_id == str(target_node.id):
                return path

            node_info = self.get_info(node_id)

            next_positions = []
            # Collect all possible positions
            next_positions.extend(
                [
                    (node_id, "south", uid)
                    for uid, nodes in node_info.get("next", {}).items()
                    if nodes
                ]
            )
            if node_info.get("children"):
                next_positions.append((node_id, "child", ""))

            for next_position in next_positions:
                found = explore(next_position, path + [next_position])
                if found is not None:
                    return found

            return None

        full_path = explore((None, "south", ""), [])
        if full_path is not None:
            return [(self.get_node(nid), p, o) for [nid, p, o] in full_path]

        return None

    def _get_all_next_nodes(self, node: AutomationNode):
        """
        Collects all next node of the give node regardless of their output.
        """

        node_info = self.get_info(node)

        return [x for sublist in node_info.get("next", {}).values() for x in sublist]

    def get_next_nodes(
        self, node: AutomationNode, output: str | None = None
    ) -> List[AutomationNode]:
        """
        Get next nodes on the given output if output is set or all outputs if not..
        """

        node_info = self.get_info(node)

        return [
            self.get_node(x)
            for uid, sublist in node_info.get("next", {}).items()
            for x in sublist
            if output is None or uid == output
        ]

    def get_children(self, node: AutomationNode) -> List[AutomationNode]:
        """
        Returns the node children.
        """

        return [self.get_node(cid) for cid in self.get_info(node).get("children", [])]

    def insert(
        self,
        node: AutomationNode,
        reference_node: AutomationNode,
        position: NodePositionType,
        output: str,
    ):
        """
        Insert a node at the given position. Rewire all necessary nodes.
        """

        output = str(output)  # When it's an UUID

        graph = self.graph

        node_info = graph.setdefault(str(node.id), {})

        new_next = None

        if reference_node is None:
            if "0" in graph:
                new_next = [graph["0"]]

            # This is the first node of the graph
            graph["0"] = node.id

            if new_next:
                node_info["next"] = {"": new_next}

            self._update_graph()
            return

        if position == "south":
            if output in self.get_info(reference_node).get("next", {}):
                new_next = self.get_info(reference_node)["next"][output]

            self.get_info(reference_node).setdefault("next", {})[output] = [node.id]

        elif position == "child":
            if "children" in self.get_info(reference_node):
                new_next = self.get_info(reference_node)["children"]

            self.get_info(reference_node)["children"] = [node.id]

        if new_next:
            node_info["next"] = {"": new_next}
        else:
            if "next" in node_info:
                del node_info["next"]

        self._update_graph()

    def remove(self, node_to_delete: AutomationNode, keep_info=False):
        """
        Remove the given node.

        :param node_to_delete: The node to delete.
        :param keep_info: doesn't delete the info dict from the graph yet if True.
        """

        graph = self.workflow.graph

        if str(node_to_delete.id) not in graph:
            # The node is already removed. Could be by a replace.
            return

        next_node_ids = self._get_all_next_nodes(node_to_delete)

        node_position_id, position, output = self.get_position(node_to_delete)

        if node_position_id is None:
            next_nodes = self._get_all_next_nodes(node_to_delete)
            if next_nodes:
                graph["0"] = next_nodes[0]
            else:
                del graph["0"]

        elif position == "south":
            graph[node_position_id]["next"][output] = _replace(
                graph[node_position_id]["next"][output],
                node_to_delete.id,
                next_node_ids,
            )
            if not graph[node_position_id]["next"][output]:
                del graph[node_position_id]["next"][output]
            if not graph[node_position_id]["next"]:
                del graph[node_position_id]["next"]
        elif position == "child":
            next_nodes = self._get_all_next_nodes(node_to_delete)
            graph[node_position_id]["children"] = _replace(
                graph[node_position_id]["children"],
                node_to_delete.id,
                next_nodes,
            )
            if not graph[node_position_id]["children"]:
                del graph[node_position_id]["children"]

        if not keep_info:
            del graph[str(node_to_delete.id)]

        self._update_graph()

    def replace(self, node_to_replace: AutomationNode, new_node: AutomationNode):
        """
        Replace a node with another at the same position.
        """

        reference_node_id, position, output = self.get_position(node_to_replace)

        node_to_replace_id = str(node_to_replace.id)
        new_node_id = str(new_node.id)

        self.graph[new_node_id] = self.graph[node_to_replace_id]

        if position == "south":
            if reference_node_id is None:
                self.graph["0"] = new_node.id
            else:
                self.graph[reference_node_id]["next"][output] = _replace(
                    self.graph[reference_node_id]["next"][output],
                    node_to_replace.id,
                    new_node.id,
                )
        elif position == "child":
            self.graph[reference_node_id]["children"] = _replace(
                self.graph[reference_node_id]["children"],
                node_to_replace.id,
                new_node.id,
            )

        del self.graph[node_to_replace_id]

        self._update_graph()

    def move(
        self,
        node_to_move: AutomationNode,
        reference_node: AutomationNode | None,
        position: NodePositionType,
        output: str,
    ):
        """
        Move a node at another given position.
        """

        output = str(output)  # When it's an UUID

        self.remove(node_to_move, keep_info=True)
        self.insert(node_to_move, reference_node, position, output)

    def migrate_graph(self, id_mapping):
        """
        Updates the node IDs and edge UIDs in the graph from the id_mapping.
        """

        migrated = {}

        def map_node(nid):
            return id_mapping["automation_workflow_nodes"][int(nid)]

        def map_output(uid):
            if uid == "":
                return ""
            return id_mapping["automation_edge_outputs"][uid]

        for key, info in self.graph.items():
            if key == "0":
                migrated["0"] = id_mapping["automation_workflow_nodes"][info]

            else:
                migrated[str(map_node(key))] = {}
                if "next" in info:
                    migrated[str(map_node(key))]["next"] = {
                        map_output(uid): [map_node(nid) for nid in nids]
                        for uid, nids in info["next"].items()
                    }
                if "children" in info:
                    migrated[str(map_node(key))]["children"] = [
                        map_node(nid) for nid in info["children"]
                    ]

        self._update_graph(migrated)

    def _get_edge_label(self, node, uid):
        """
        Returns the label of the given edge uid for the given node.
        """

        edges = node.service.get_type().get_edges(node.service.specific)
        return edges[uid]["label"]

    def labeled_graph(self):
        """
        Generate a graph representation that doesn't depends on the node IDs and that is
        reliable between test executions.
        """

        used_label = {}

        def label(node_id):
            node_id = str(node_id)
            label = self.get_node(node_id).get_label()

            while used_label.setdefault(label, node_id) != node_id:
                label += "-"

            return label

        result = {}
        for key, node_info in self.graph.items():
            if key == "0":
                result[key] = label(node_info)
            else:
                result[label(key)] = {}
                if "children" in node_info:
                    result[label(key)]["children"] = [
                        label(id) for id in node_info["children"]
                    ]
                if "next" in node_info:
                    result[label(key)]["next"] = {
                        self._get_edge_label(self.get_node(key), o): [
                            label(id) for id in n
                        ]
                        for o, n in node_info["next"].items()
                    }

        return result
