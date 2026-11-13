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


@dataclass
class NodeDispatchRetry:
    """
    Returned by dispatch_node() when the attempt failed and the node's error
    policy allows another one. The Celery task turns it into a delayed retry
    of itself, outside the dispatch transaction.
    """

    node_id: int
    history_id: int
    # The attempt that just failed, 1-based.
    attempt: int
    # Seconds to wait before the next attempt.
    countdown: int


class AutomationNodeDict(TypedDict):
    id: int
    type: str
    label: str
    note: str
    service: dict
    workflow_id: int
    on_failure: str
    max_retries: int
    retry_condition: dict


@dataclass
class PendingNodeNotDue:
    """
    Returned by resume_pending_node() when the waiting node is not due yet. The
    Celery task turns it into a delayed retry of itself.
    """

    # Seconds to wait before checking again: the time left, cut to one chunk.
    countdown: int


@dataclass
class PendingNodeAlreadyClaimed:
    """
    Returned by resume_pending_node() when another delivery of the resume task
    (a redelivered message, or the recovery sweep) already resumed the node.
    The Celery task drops itself with `Ignore`, which also drops its copy of the
    run's chain so the run is not completed twice, or early.
    """
