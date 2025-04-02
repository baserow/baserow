from typing import TypedDict


class AutomationDict(TypedDict):
    id: int
    name: str
    order: int
    type: str


class AutomationWorkflowDict(TypedDict):
    id: int
    name: str
    order: int
