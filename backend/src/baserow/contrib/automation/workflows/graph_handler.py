from collections import defaultdict
from copy import deepcopy


class NodeGraphHandler:
    def __init__(self, workflow):
        self.workflow = workflow

    def _update_graph(self):
        print("new graph", self.workflow.graph)
        self.workflow.save(update_fields=["graph"])

    @property
    def graph(self):
        return self.workflow.graph

    def get_info(self, node):
        from baserow.contrib.automation.nodes.models import AutomationNode

        if isinstance(node, AutomationNode):
            return self.graph[str(node.id)]

        return self.graph[str(node)]

    def get_node(self, position_node, position, output):
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        output = str(output)

        if position == "south":
            # First node
            if position_node is None:
                return AutomationNodeHandler().get_node(self.graph["0"])

            next_nodes = self.get_info(position_node).get("next", {}).get(output, [])
            if next_nodes:
                return AutomationNodeHandler().get_node(next_nodes[0])

        elif position == "child":
            children = self.get_info(position_node).get("child", [])
            if children:
                return AutomationNodeHandler().get_node(children[0])

        else:
            raise Exception("Unexpected position")

        return None

    def get_last_position(self):
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        if self.graph.get("0") is None:
            return [None, "south", ""]

        def search_last(node_id):
            next_nodes = self.get_info(node_id).get("next", {}).get("", [])
            if not next_nodes:
                return [AutomationNodeHandler().get_node(node_id), "south", ""]
            else:
                return search_last(next_nodes[0])

        return search_last(self.graph["0"])

    def get_position(self, node):
        for node_id, value in self.graph.items():
            if node_id == "0" or node_id == str(node.id):
                continue

            for output_uid, next_nodes in value.get("next", {}).items():
                if node.id in next_nodes:
                    return [node_id, "south", output_uid]

            if node.id in value.get("child", []):
                return [node_id, "child", ""]

        # should not happen unless it's the trigger
        return [None, "south", ""]

    def insert(self, node, position_node, position, output):
        output = str(output)  # When it's an UUID

        graph = self.workflow.graph

        print(
            "insert",
            node.id,
            position_node.id if position_node else None,
            position,
            output,
        )
        print("current graph", graph)

        node_info = graph.setdefault(str(node.id), {})

        # TODO specific position?
        if position_node is None:
            if "0" in self.workflow.graph:
                raise Exception("Trigger already there")

            if not node.get_type().is_workflow_trigger:
                raise Exception("This is not a trigger")

            print("we create the trigger")
            # this is the first node and it's a trigger
            graph["0"] = node.id

            # The graph is updated so we save it.
            self._update_graph()

            return {str(node.id): None, "0": None}, {
                str(node.id): node_info,
                "0": node.id,
            }

        position_node_info = graph[str(position_node.id)]

        if position == "south":
            # outputs = position_node.service.get_type().get_outputs(
            #    position_node.specific
            # )
            # TODO check output in outputs?

            previous_next = None

            if "next" in position_node_info and output in position_node_info["next"]:
                previous_next = position_node_info["next"][output]

            position_node_info.setdefault("next", {})[output] = [node.id]

            if previous_next:
                node_info["next"] = {"": previous_next}

        elif position == "child":
            previous_children = []

            if "child" in position_node_info:
                previous_children = position_node_info["child"]

            position_node_info["child"] = [node.id]

            if previous_children:
                node_info["next"] = {"": previous_children}
        else:
            raise Exception("Unknown position")

        self._update_graph()

    def _get_all_next_nodes(self, node):
        node_info = self.graph[str(node.id)]

        return [x for sublist in node_info.get("next", {}).values() for x in sublist]

    def remove(self, node_to_delete):
        graph = self.workflow.graph

        print("remove node", node_to_delete.id)

        if str(node_to_delete.id) not in graph:
            # The node is already removed. Could be by a replace.
            return

        next_node_ids = self._get_all_next_nodes(node_to_delete)

        print("initial graph before remove", graph)
        print("next_node_ids", next_node_ids)

        node_position_id, position, output = self.get_position(node_to_delete)

        if position == "south":
            next_nodes = graph[node_position_id]["next"][output]
            index = next_nodes.index(node_to_delete.id)

            graph[node_position_id]["next"][output] = (
                next_nodes[:index] + next_node_ids + next_nodes[index + 1 :]
            )
        elif position == "child":
            next_nodes = self._get_all_next_nodes(node_to_delete)
            graph[node_position_id]["child"] = next_nodes
        else:
            raise Exception("Unknown position")

        del graph[str(node_to_delete.id)]

        self._update_graph()

    def move(self, node_to_move, position_node, position, output):
        output = str(output)  # When it's an UUID

        node_info = deepcopy(self.graph[str(node_to_move.id)])

        self.remove(node_to_move)
        self.insert(node_to_move, position_node, position, output)

        # We keep the children
        if "child" in node_info:
            self.graph[str(node_to_move.id)]["child"] = node_info["child"]

        self._update_graph()

    def labeled_graph(self):
        from baserow.contrib.automation.nodes.handler import (
            AutomationNodeHandler,
        )

        def get_node(node_id):
            return AutomationNodeHandler().get_node(node_id)

        def label(node_id):
            return get_node(node_id).get_label()

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
                    service = get_node(key).service.specific
                    edges = service.get_type().get_edges(service)
                    result[label(key)]["next"] = {
                        edges[o]["label"]: [label(id) for id in n]
                        for o, n in node_info["next"].items()
                    }

        return result
