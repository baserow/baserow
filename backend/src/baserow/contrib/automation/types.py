from typing import List, NotRequired, TypedDict

from baserow.contrib.automation.nodes.types import AutomationNodeDict


class AutomationWorkflowDict(TypedDict):
    id: int
    name: str
    order: int


class AutomationDict(TypedDict):
    id: int
    name: str
    order: int
    type: str
    workflows: List[AutomationWorkflowDict]


class AutomationWorkflowNodeHierarchyDict(TypedDict):
    workflow: AutomationWorkflowDict
    previous_node: NotRequired[AutomationNodeDict]
    node: AutomationNodeDict
    next_node: NotRequired[AutomationNodeDict]
