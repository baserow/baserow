from typing import List, TypedDict

from baserow.contrib.automation.nodes.types import AutomationNodeDict


class AutomationWorkflowDict(TypedDict):
    id: int
    name: str
    order: int
    nodes: List[AutomationNodeDict]


class AutomationDict(TypedDict):
    id: int
    name: str
    order: int
    type: str
    workflows: List[AutomationWorkflowDict]
