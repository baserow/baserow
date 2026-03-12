from dataclasses import dataclass
from typing import List, NewType, TypedDict, TypeVar, Union

from baserow.contrib.builder.types import ElementDict
from baserow.core.graph.types import GraphPointPositionType

from ..workflow_actions.models import BuilderWorkflowAction
from .models import Element, RecordSelectorElement, RepeatElement, TableElement

ElementDictSubClass = TypeVar("ElementDictSubClass", bound=ElementDict)
ElementSubClass = TypeVar("ElementSubClass", bound=Element)

ElementForUpdate = NewType("ElementForUpdate", Element)

CollectionElementSubClass = Union[TableElement, RepeatElement, RecordSelectorElement]


class ElementsAndWorkflowActions(TypedDict):
    elements: List[Element]
    workflow_actions: List[BuilderWorkflowAction]


@dataclass
class ElementMove:
    element: Element
    previous_reference_element: Element | None
    previous_position: GraphPointPositionType
