from dataclasses import dataclass
from typing import NewType, TypedDict

from baserow.contrib.automation.nodes.models import AutomationNode

AutomationNodeForUpdate = NewType("AutomationNodeForUpdate", AutomationNode)


@dataclass
class UpdatedAutomationNode:
    node: AutomationNode
    original_values: dict[str, any]
    new_values: dict[str, any]


class AutomationNodeDict(TypedDict):
    id: int
    order: float
    workflow_id: int
    parent_node_id: int
    previous_node_id: int
    previous_node_output: str
