from dataclasses import dataclass
from typing import NewType, Optional, TypedDict

from baserow.contrib.automation.nodes.models import AutomationNode

AutomationNodeForUpdate = NewType("AutomationNodeForUpdate", AutomationNode)


@dataclass
class UpdatedAutomationNode:
    node: AutomationNode
    original_values: dict[str, any]
    new_values: dict[str, any]


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    order: float
    service_id: Optional[int]
    workflow_id: int
    parent_node_id: int
    previous_node_id: int
    previous_node_output: str
