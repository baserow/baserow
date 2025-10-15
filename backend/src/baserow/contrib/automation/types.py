from typing import List, TypedDict

from baserow.contrib.automation.nodes.types import AutomationNodeDict
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.core.integrations.types import IntegrationDictSubClass


class AutomationWorkflowDict(TypedDict):
    id: int
    name: str
    order: int
    nodes: List[AutomationNodeDict]
    state: WorkflowState
    graph: dict


class AutomationDict(TypedDict):
    id: int
    name: str
    order: int
    type: str
    workflows: List[AutomationWorkflowDict]
    integrations: List[IntegrationDictSubClass]
