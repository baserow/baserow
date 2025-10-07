from dataclasses import dataclass
from typing import Any, List, NewType, TypedDict

from baserow.contrib.automation.nodes.models import AutomationActionNode, AutomationNode

AutomationNodeForUpdate = NewType("AutomationNodeForUpdate", AutomationNode)


@dataclass
class UpdatedAutomationNode:
    node: AutomationNode
    original_values: dict[str, Any]
    new_values: dict[str, Any]


@dataclass
class ReplacedAutomationNode:
    node: AutomationNode
    original_node_id: int
    original_node_type: str


@dataclass
class NextAutomationNodeValues:
    id: int
    previous_node_id: int
    previous_node_output: str


@dataclass
class AutomationNodeDuplication:
    source_node: AutomationNode
    source_node_next_nodes_values: List[NextAutomationNodeValues]
    duplicated_node: AutomationNode
    duplicated_node_next_nodes_values: List[NextAutomationNodeValues]


@dataclass
class AutomationNodeMove:
    # The node we're trying to move.
    node: AutomationActionNode
    # A list of origin *and* destination next nodes
    next_node_updates: List[AutomationActionNode]
    # The original position & output of the node before the move.
    origin_previous_node_id: int
    origin_previous_node_output: str
    # The pre-move values of the next nodes after `node`, at the original position.
    origin_old_next_nodes_values: List[NextAutomationNodeValues]
    # The post-move values of the next nodes after `node`, at the original position.
    origin_new_next_nodes_values: List[NextAutomationNodeValues]
    # The destination position & output of the node after the move.
    destination_previous_node_id: int
    destination_previous_node_output: str
    # The pre-move values of the next nodes after
    # `destination_previous_node_id`, at the new position.
    destination_old_next_nodes_values: List[NextAutomationNodeValues]
    # The post-move values of the next nodes after
    # `destination_previous_node_id`, at the new position.
    destination_new_next_nodes_values: List[NextAutomationNodeValues]


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    order: float
    workflow_id: int
    parent_node_id: int
    previous_node_id: int
    previous_node_output: str
