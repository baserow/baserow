from dataclasses import dataclass
from typing import NewType

from baserow.contrib.automation.nodes.models import AutomationNode

AutomationNodeForUpdate = NewType("AutomationNodeForUpdate", AutomationNode)


@dataclass
class UpdatedAutomationNode:
    node: AutomationNode
    original_values: dict[str, any]
    new_values: dict[str, any]
