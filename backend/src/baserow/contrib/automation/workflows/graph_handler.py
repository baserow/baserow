from typing import Iterable

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import GraphPointPosition, GraphPointPositionType


class AutomationWorkflowGraphHandler(BaseGraphHandler):
    """
    The automation workflow graph handler is responsible for managing
    the graph of an automation workflow.
    """

    base_point_class = AutomationNode
    outputs_id_mapping = "automation_edge_outputs"
    instance_id_mapping = "automation_workflow_nodes"
    does_not_exist_exception = AutomationNodeDoesNotExist

    def get_all_points(self) -> Iterable[AutomationNode]:
        return AutomationNodeHandler().get_nodes(self.instance)

    def get_positions_in_execution_order(
        self, nodes: Iterable[AutomationNode]
    ) -> list[
        tuple[AutomationNode, AutomationNode | None, GraphPointPositionType, str]
    ]:
        """
        The nodes of the workflow in execution order: the trigger, then each node
        after the one before it, a container's children before the nodes that
        follow it. A node's outputs are followed in the order of its service's
        edges, so a router's branches come in their order and the default one last.
        An output the service doesn't have sorts with its first edge, keeping the
        stored order between them. Each node is listed once, so a corrupted graph
        terminates.

        :param nodes: The nodes to list. A node not in it is skipped, with the
            nodes only reachable through it.
        :returns: For each node, the node itself, the node it is placed after or
            inside (None for the trigger), the position ("south" after it, "child"
            inside it) and the output or children edge of that node.
        """

        nodes_by_id = {node.id: node for node in nodes}
        graph = self.graph
        ordered: list[
            tuple[AutomationNode, AutomationNode | None, GraphPointPositionType, str]
        ] = []
        visited: set[int] = set()
        trigger_id = graph.get(self.GRAPH_ROOT_KEY)
        # Depth first with an explicit stack, so a long chain can't reach the
        # recursion limit. Each node's successors are pushed in reverse.
        stack = (
            []
            if trigger_id is None
            else [(trigger_id, None, GraphPointPosition.SOUTH, "")]
        )
        while stack:
            node_id, previous, position, output = stack.pop()
            if node_id in visited or node_id not in nodes_by_id:
                continue
            visited.add(node_id)
            node = nodes_by_id[node_id]
            ordered.append((node, previous, position, output))
            info = graph.get(str(node_id), {})
            following = [
                (child_id, node, GraphPointPosition.CHILD, edge)
                for edge, child_ids in self._get_children_dict(info).items()
                for child_id in child_ids
            ]
            next_outputs = list(info.get("next", {}).items())
            # Only a node with several outputs needs its service to order them.
            if len(next_outputs) > 1:
                order = list(node.service.get_type().get_edges(node.service.specific))
                next_outputs.sort(
                    key=lambda item: order.index(item[0]) if item[0] in order else 0
                )
            following += [
                (next_id, node, GraphPointPosition.SOUTH, next_output)
                for next_output, next_ids in next_outputs
                for next_id in next_ids
            ]
            stack.extend(reversed(following))
        return ordered
