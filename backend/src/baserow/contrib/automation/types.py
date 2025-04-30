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


class AutomationNodeDict(TypedDict):
    id: int
    order: int
    type: str
    workflow_id: int
    previous_node_id: int
    parent_node_id: int
    previous_node_output: str
