from collections import defaultdict
from copy import deepcopy


def _replace(list_, item_to_replace, replacement):
    index = list_.index(item_to_replace)

    return (
        list_[:index]
        + (replacement if isinstance(replacement, list) else [replacement])
        + list_[index + 1 :]
    )


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

        node_id = node
        if isinstance(node, AutomationNode):
            node_id = node.id

        return self.graph[str(node_id)]

    def set_info(self, node, info):
        from baserow.contrib.automation.nodes.models import AutomationNode

        node_id = node
        if isinstance(node, AutomationNode):
            node_id = node.id

        self.graph[str(node_id)] = info

    def get_node_id(self, position_node, position, output):
        output = str(output)

        if position == "south":
            # First node
            if position_node is None:
                return self.graph["0"]

            next_nodes = self.get_info(position_node).get("next", {}).get(output, [])
            if next_nodes:
                return next_nodes[0]

        elif position == "child":
            children = self.get_info(position_node).get("child", [])
            if children:
                return children[0]

        else:
            raise Exception("Unexpected position")

        return None

    def get_node(self, position_node, position, output):
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        node_id = self.get_node_id(position_node, position, output)

        return AutomationNodeHandler().get_node(node_id)

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
        for node_id, node_info in self.graph.items():
            if node_id == "0" or node_id == str(node.id):
                continue

            for output_uid, next_nodes in node_info.get("next", {}).items():
                if node.id in next_nodes:
                    return [node_id, "south", output_uid]

                if node.id in node_info.get("child", []):
                    return [node_id, "child", ""]

        # Should happen only for trigger
        return [None, "south", ""]

    def get_previous_positions(self, target_node):
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        def explore(current_position, path):
            node_id = self.get_node_id(*current_position)

            if str(node_id) == str(target_node.id):
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
            [AutomationNodeHandler().get_node(nid), p, o]
            for [nid, p, o] in explore([None, "south", ""], [])
        ]

    def insert(self, node, position_node, position, output):
        output = str(output)  # When it's an UUID

        graph = self.graph

        print(
            "insert",
            node.id,
            position_node.id if position_node else None,
            position,
            output,
        )
        print("current graph", graph)

        node_info = graph.setdefault(str(node.id), {})

        # position_node_info = graph[str(position_node.id)]

        new_next = None

        if position == "south":
            if position_node is None:
                if "0" in self.graph:
                    raise Exception("Trigger already there")

                if not node.get_type().is_workflow_trigger:
                    raise Exception("This is not a trigger")

                print("we create the trigger")
                # this is the first node and it's a trigger
                graph["0"] = node.id

            else:
                if output not in position_node.service.get_type().get_edges(position_node.service.specific):
                    raise Exception("Output doesnt exist on node")

                if output in self.get_info(position_node).get("next", {}):
                    new_next = self.get_info(position_node)["next"][output]

                self.get_info(position_node).setdefault("next", {})[output] = [node.id]

        elif position == "child":
            if "child" in self.get_info(position_node):
                new_next = self.get_info(position_node)["child"]

            self.get_info(position_node)["child"] = [node.id]

        else:
            raise Exception("Unknown position")

        if new_next:
            node_info["next"] = {"": new_next}
        else:
            if "next" in node_info:
                del node_info["next"]

        self._update_graph()

    def _get_all_next_nodes(self, node):
        node_info = self.graph[str(node.id)]

        return [x for sublist in node_info.get("next", {}).values() for x in sublist]

    def remove(self, node_to_delete, keep_info=False):
        graph = self.workflow.graph

        print("remove node", node_to_delete.id)

        if str(node_to_delete.id) not in graph:
            # The node is already removed. Could be by a replace.
            return

        next_node_ids = self._get_all_next_nodes(node_to_delete)

        # TODO can't remove a trigger
        # TODO cant't remove a node with children

        print("initial graph before remove", graph)
        print("next_node_ids", next_node_ids)

        node_position_id, position, output = self.get_position(node_to_delete)

        print("found position of the node", node_position_id, position, output)

        if position == "south":
            # Todo remove trigger
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
        position_node_id, position, output = self.get_position(node_to_replace)

        node_to_replace_id = str(node_to_replace.id)
        new_node_id = str(new_node.id)

        self.graph[new_node_id] = self.graph[node_to_replace_id]

        if position == "south":
            if position_node_id is None:
                self.graph["0"] = new_node_id
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
        output = str(output)  # When it's an UUID

        self.remove(node_to_move, keep_info=True)
        self.insert(node_to_move, position_node, position, output)

    def labeled_graph(self):
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        used_label = {}

        def get_node(node_id):
            return AutomationNodeHandler().get_node(node_id)

        def label(node_id):
            node_id = str(node_id)
            label = get_node(node_id).get_label()

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
                    service = get_node(key).service.specific
                    edges = service.get_type().get_edges(service)
                    result[label(key)]["next"] = {
                        edges[o]["label"]: [label(id) for id in n]
                        for o, n in node_info["next"].items()
                    }

        return result
