from dataclasses import dataclass
from typing import Any, Literal, NewType, TypeAlias, TypedDict

from django.db import models

from baserow.contrib.automation.nodes.models import AutomationActionNode, AutomationNode

AutomationNodeForUpdate = NewType("AutomationNodeForUpdate", AutomationNode)


class NodePosition(models.TextChoices):
    SOUTH = "south", "South"
    CHILD = "child", "Child"


NodePositionType = Literal["south", "child"]

NodePositionTriplet: TypeAlias = tuple[AutomationNode | None, NodePositionType, str]


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
    previous_position: NodePositionType
    previous_output: str


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    label: str
    service: dict
    workflow_id: int
