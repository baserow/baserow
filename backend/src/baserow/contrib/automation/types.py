from typing import List, NotRequired, TypedDict

from baserow.contrib.automation.nodes.types import AutomationNodeDict
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.core.graph.types import SerializedGraph
from baserow.core.integrations.types import IntegrationDictSubClass


class AutomationWorkflowDict(TypedDict):
    # Only internal copies carry it, see the export.
    untrusted_content: NotRequired[bool]
    id: int
    name: str
    order: int
    nodes: List[AutomationNodeDict]
    state: WorkflowState
    graph: SerializedGraph
    notification_recipient_emails: List[str]


class AutomationDict(TypedDict):
    id: int
    name: str
    order: int
    type: str
    workflows: List[AutomationWorkflowDict]
    integrations: List[IntegrationDictSubClass]
