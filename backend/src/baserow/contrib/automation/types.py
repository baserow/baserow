from typing import TypedDict, List


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
