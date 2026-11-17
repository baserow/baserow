from typing import Callable, Container, Iterable

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
        self,
        node_ids: Container[int],
        output_order: Callable[[int], list[str]],
    ) -> list[tuple[int, int | None, GraphPointPositionType, str]]:
        """
        The nodes of the workflow in execution order: the trigger, then each node
        after the one before it, a container's children before the nodes that
        follow it. Each node is listed once, so a corrupted graph terminates.

        :param node_ids: The nodes to list. A node not in it is skipped, with the
            nodes only reachable through it.
        :param output_order: Returns the outputs of a node in the order to follow
            them. An output it doesn't name sorts with the first one it names,
            keeping the stored order between them.
        :returns: For each node, its ID, the ID of the node it is placed after or
            inside (None for the trigger), the position ("south" after it, "child"
            inside it) and the output or children edge of that node.
        """

        graph = self.graph
        ordered: list[tuple[int, int | None, GraphPointPositionType, str]] = []
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
            node_id, previous_id, position, output = stack.pop()
            if node_id in visited or node_id not in node_ids:
                continue
            visited.add(node_id)
            ordered.append((node_id, previous_id, position, output))
            info = graph.get(str(node_id), {})
            following = [
                (child_id, node_id, GraphPointPosition.CHILD, edge)
                for edge, child_ids in self._get_children_dict(info).items()
                for child_id in child_ids
            ]
            order = output_order(node_id)
            next_outputs = sorted(
                info.get("next", {}).items(),
                key=lambda item: order.index(item[0]) if item[0] in order else 0,
            )
            following += [
                (next_id, node_id, GraphPointPosition.SOUTH, next_output)
                for next_output, next_ids in next_outputs
                for next_id in next_ids
            ]
            stack.extend(reversed(following))
        return ordered
