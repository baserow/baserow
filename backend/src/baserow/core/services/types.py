from dataclasses import dataclass, field
from typing import NamedTuple, NewType, Optional, TypedDict, TypeVar

from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.services.models import Service


class ServiceDict(TypedDict):
    id: int
    integration_id: int
    type: str
    sample_data: dict


class ServiceFilterDict(TypedDict):
    id: Optional[int]
    service: int
    type: str
    value: str


class ServiceSortDict(TypedDict):
    id: Optional[int]
    service: int
    field: int
    order: str


@dataclass
class DispatchResult:
    data: dict = field(default_factory=dict)
    status: int = 200
    output_uid: str = ""


@dataclass
class UpdatedService:
    service: Service
    original_service_values: dict[str, any]
    new_service_values: dict[str, any]


class FormulaToResolve(NamedTuple):
    key: str
    formula: BaserowFormulaObject
    ensurer: callable
    label: str


ServiceDictSubClass = TypeVar("ServiceDictSubClass", bound="ServiceDict")

ServiceFilterDictSubClass = TypeVar(
    "ServiceFilterDictSubClass", bound="ServiceFilterDict"
)

ServiceSortDictSubClass = TypeVar("ServiceSortDictSubClass", bound="ServiceSortDict")

ServiceSubClass = TypeVar("ServiceSubClass", bound="Service")

ServiceForUpdate = NewType("ServiceForUpdate", Service)

RuntimeFormulaContextSubClass = TypeVar(
    "RuntimeFormulaContextSubClass", bound=RuntimeFormulaContext
)
