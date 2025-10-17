from dataclasses import dataclass
from typing import Any, NewType, TypedDict

from baserow.contrib.automation.nodes.models import AutomationActionNode, AutomationNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow

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
    previous_position_node: AutomationActionNode | None
    previous_position: str
    previous_output: str


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    label: str
    service: dict
    workflow_id: int
