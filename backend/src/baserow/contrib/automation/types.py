from typing import List, TypedDict


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
