from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from baserow.core.services.types import DispatchResult
from baserow.core.workflow_actions.types import WorkflowActionDict

if TYPE_CHECKING:
    from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction


class DatabaseWorkflowActionDict(WorkflowActionDict):
    field_id: int


@dataclass
class DispatchedWorkflowAction:
    """A server-side action and what its dispatch returned."""

    workflow_action: "DatabaseWorkflowAction"
    result: DispatchResult


@dataclass
class WorkflowActionsDispatchResult:
    """
    What one click produced: what already ran on the server, and the
    frontend-only actions the browser still has to run itself, both in order.
    """

    dispatched: List[DispatchedWorkflowAction] = field(default_factory=list)
    client_actions: List["DatabaseWorkflowAction"] = field(default_factory=list)
