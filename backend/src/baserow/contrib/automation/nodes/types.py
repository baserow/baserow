from dataclasses import dataclass, field
from typing import Any, NewType, TypedDict

from baserow.contrib.automation.nodes.models import AutomationNode

AutomationNodeForUpdate = NewType("AutomationNodeForUpdate", AutomationNode)


@dataclass
class UpdatedAutomationNode:
    # The `node` which was updated.
    # This *could* be a new instance if the type changed.
    node: AutomationNode
    # The `node_id` of the node.
    # If the type changed, this will be the old node's ID.
    node_id: int
    # The `type` of the node.
    # If the type changed, this will be the old node's type.
    node_type: str
    # Whether the node `type` was changed.
    type_changed: bool = field(default=False)
    # The `original_node_id` is the ID of the old node if the
    # type changed, otherwise it is None.
    original_node_id: int = field(default=None)
    # The `original_node_type` is the type of the old node if the
    # type changed, otherwise it is None.
    original_node_type: str = field(default="")
    # The `original_values` are the values of the node
    # before the update. Only set if the isn't changing.
    original_values: dict[str, Any] = field(default_factory=dict)
    # The `new_values` are the values of the node
    # after the update. Only set if the isn't changing.
    new_values: dict[str, Any] = field(default_factory=dict)


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    order: float
    workflow_id: int
    parent_node_id: int
    previous_node_id: int
    previous_node_output: str
