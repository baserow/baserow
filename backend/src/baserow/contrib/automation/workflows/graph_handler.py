from baserow.contrib.automation.nodes.exceptions import AutomationNodeMissingOutput
from baserow.contrib.automation.nodes.models import AutomationNode


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
        "3": {"next": {"": ["output edge 1"]}},
        "5": {},
        "4": {"next": {"": [6]}},
        "6": {"child": [7]}
        "7": {}
    }
    ```

    The key is the ID of a node except for the key '0' that indicates the ID of the
    first node of the graph.

    For each node, `next` is the dict keyed by edge UUIDs and valued by the list of
    node ID on this edge. For now only one node is possible per output.

    `child` is an array of children for the container node.

    This graph structure use triplet of position to identify the position of a node.
    A triplet looks like [position_node, position, output].

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

    def _update_graph(self):
        """
        Save the workflow graph.
        """

        self.workflow.save(update_fields=["graph"])

    def get_info(self, node):
        """
        Returns the info dict for the given node.
        """

        from baserow.contrib.automation.nodes.models import AutomationNode

        node_id = node
        if isinstance(node, AutomationNode):
            node_id = node.id

        return self.graph[str(node_id)]

    def _get_node_map(self):
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        return {n.id: n for n in AutomationNodeHandler().get_nodes(self.workflow)}

    def get_node(self, node_id):
        """
        Return the node instance for the given node ID.
        """

        return self._get_node_map()[int(node_id)]

    def get_node_at_position(
        self, position_node: AutomationNode, position: str, output: str
    ):
        """
        Returns the node at the given position in the graph.

        :param position_node: The node used as reference for the position.
        :param position: The direction relative to the reference node.
        :param output: The output of the reference node to use.
        """

        output = str(output)

        if position == "south":
            # First node
            if position_node is None:
                return self.get_node(self.graph["0"])

            next_nodes = self.get_info(position_node).get("next", {}).get(output, [])
            if next_nodes:
                return self.get_node(next_nodes[0])

        elif position == "child":
            children = self.get_info(position_node).get("child", [])
            if children:
                return self.get_node(children[0])

        else:
            raise Exception("Unexpected position")

        return None

    def get_last_position(self):
        """
        Return the last position of the graph if we follow the default edge ("") of
        each node. Mostly used to place nodes in tests.
        """

        if self.graph.get("0") is None:
            return [None, "south", ""]

        def search_last(node_id):
            next_nodes = self.get_info(node_id).get("next", {}).get("", [])
            if not next_nodes:
                return [self.get_node(node_id), "south", ""]
            else:
                return search_last(next_nodes[0])

        return search_last(self.graph["0"])

    def get_position(self, node: AutomationNode):
        """
        Returns the position of the given node.
        """

        if node.id == self.graph.get("0", None):
            # it's the trigger
            return [None, "south", ""]

        for node_id, node_info in self.graph.items():
            if node_id == "0" or node_id == str(node.id):
                continue

            for output_uid, next_nodes in node_info.get("next", {}).items():
                if node.id in next_nodes:
                    return [node_id, "south", output_uid]

            if node.id in node_info.get("child", []):
                return [node_id, "child", ""]

        raise Exception("Node not found in the graph")

    def get_previous_positions(self, target_node: AutomationNode):
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
                [[node_id, "south", uid] for uid in node_info.get("next", {}).keys()]
            )
            if "child" in node_info:
                next_positions.append([node_id, "child", ""])

            for next_position in next_positions:
                found = explore(next_position, path + [next_position])
                if found is not None:
                    return found

            return None

        return [
            [self.get_node(nid), p, o]
            for [nid, p, o] in explore([None, "south", ""], [])
        ]

    def _get_all_next_nodes(self, node):
        """
        Collects all next node of the give node regardless of their output.
        """

        node_info = self.get_info(node)

        return [x for sublist in node_info.get("next", {}).values() for x in sublist]

    def get_next_nodes(self, node):
        """
        Get all next nodes regardless of their output.
        """

        return [self.get_node(n) for n in self._get_all_next_nodes(node)]

    def insert(self, node, position_node, position, output):
        """
        Insert a node at the given position. Rewire all necessary nodes.
        """

        output = str(output)  # When it's an UUID

        graph = self.graph

        node_info = graph.setdefault(str(node.id), {})

        new_next = None

        if position_node is None:
            if "0" in self.graph:
                raise Exception("Trigger already there")

            if not node.get_type().is_workflow_trigger:
                raise Exception("This is not a trigger")

            # this is the first node and it's a trigger
            graph["0"] = node.id

            self._update_graph()
            return

        if node.get_type().is_workflow_trigger:
            raise Exception("Trigger must be the first node")

        if position == "south":
            if output not in position_node.service.get_type().get_edges(
                position_node.service.specific
            ):
                raise AutomationNodeMissingOutput(
                    f"Output {output} doesn't exist on node {position_node.id}"
                )

            if output in self.get_info(position_node).get("next", {}):
                new_next = self.get_info(position_node)["next"][output]

            self.get_info(position_node).setdefault("next", {})[output] = [node.id]

        elif position == "child":
            if "child" in self.get_info(position_node):
                new_next = self.get_info(position_node)["child"]

            self.get_info(position_node)["child"] = [node.id]
            # TODO check one of the parent isn't the node itself

        else:
            raise Exception("Unknown position")

        if new_next:
            node_info["next"] = {"": new_next}
        else:
            if "next" in node_info:
                del node_info["next"]

        self._update_graph()

    def remove(self, node_to_delete, keep_info=False):
        """Remove the given node."""

        graph = self.workflow.graph

        if str(node_to_delete.id) not in graph:
            # The node is already removed. Could be by a replace.
            return

        next_node_ids = self._get_all_next_nodes(node_to_delete)

        # TODO can't remove a trigger
        # TODO cant't remove a node with children
        # TODO cant't remove a node with next nodes

        node_position_id, position, output = self.get_position(node_to_delete)

        if position == "south":
            # TODO remove trigger
            graph[node_position_id]["next"][output] = _replace(
                graph[node_position_id]["next"][output],
                node_to_delete.id,
                next_node_ids,
            )
        elif position == "child":
            next_nodes = self._get_all_next_nodes(node_to_delete)
            graph[node_position_id]["child"] = _replace(
                graph[node_position_id]["child"],
                node_to_delete.id,
                next_nodes,
            )
        else:
            raise Exception("Unknown position")

        if not keep_info:
            del graph[str(node_to_delete.id)]

        self._update_graph()

    def replace(self, node_to_replace, new_node):
        """
        Replace a node with another at the same position.
        """

        position_node_id, position, output = self.get_position(node_to_replace)

        node_to_replace_id = str(node_to_replace.id)
        new_node_id = str(new_node.id)

        self.graph[new_node_id] = self.graph[node_to_replace_id]

        if position == "south":
            if position_node_id is None:
                self.graph["0"] = new_node.id
            else:
                self.graph[position_node_id]["next"][output] = _replace(
                    self.graph[position_node_id]["next"][output],
                    node_to_replace.id,
                    new_node.id,
                )
        elif position == "child":
            self.graph[position_node_id]["child"] = _replace(
                self.graph[position_node_id]["child"],
                node_to_replace.id,
                new_node.id,
            )
        else:
            raise Exception("Unknown position")

        del self.graph[node_to_replace_id]

        self._update_graph()

    def move(self, node_to_move, position_node, position, output):
        """
        Move a node at another given position.
        """

        output = str(output)  # When it's an UUID

        self.remove(node_to_move, keep_info=True)
        self.insert(node_to_move, position_node, position, output)

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
                if "child" in node_info:
                    result[label(key)]["child"] = [
                        label(id) for id in node_info["child"]
                    ]
                if "next" in node_info:
                    service = self.get_node(key).service.specific
                    edges = service.get_type().get_edges(service)
                    result[label(key)]["next"] = {
                        edges[o]["label"]: [label(id) for id in n]
                        for o, n in node_info["next"].items()
                    }

        return result
