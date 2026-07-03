from dataclasses import dataclass, field
from typing import Any, NewType, TypedDict

from baserow.contrib.automation.nodes.models import AutomationActionNode, AutomationNode
from baserow.core.graph.types import GraphPointPositionType

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
class AutomationNodeMove:
    # The node we're trying to move.
    node: AutomationActionNode
    previous_reference_node: AutomationActionNode | None
    previous_position: GraphPointPositionType
    previous_output: str
    # "Go to node" links the move invalidated and cleared, as a list of
    # (goto_node_id, previous_destination_node_id) tuples. Captured so the move
    # action can restore them on undo.
    cleared_goto_links: list[tuple[int, int]] = field(default_factory=list)


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    label: str
    service: dict
    workflow_id: int
