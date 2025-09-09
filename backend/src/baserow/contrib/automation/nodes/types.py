from dataclasses import dataclass
from typing import Any, List, NewType, TypedDict

from baserow.contrib.automation.nodes.models import AutomationNode

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


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    order: float
    workflow_id: int
    parent_node_id: int
    previous_node_id: int
    previous_node_output: str
