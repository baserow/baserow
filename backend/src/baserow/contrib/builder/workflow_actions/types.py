from dataclasses import dataclass
from typing import Any, Dict

from baserow.core.workflow_actions.models import WorkflowAction
from baserow.core.workflow_actions.types import WorkflowActionDict


class BuilderWorkflowActionDict(WorkflowActionDict):
    page_id: int
    element_id: int
    event: str


@dataclass
class UpdatedBuilderWorkflowAction:
    workflow_action: WorkflowAction
    original_values: Dict[str, Any]
    new_values: Dict[str, Any]
