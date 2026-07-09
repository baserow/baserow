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
    # Reversible modifications node types made to reconcile the workflow after
    # the move (e.g. clearing now-invalid "Go to node" links), keyed by node
    # type. Captured so the move action can revert them on undo.
    move_extra_data: dict[str, Any] = field(default_factory=dict)


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    label: str
    service: dict
    workflow_id: int
