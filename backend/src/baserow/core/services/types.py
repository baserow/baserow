from dataclasses import dataclass
from typing import NewType, Optional, TypedDict, TypeVar

from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext
from baserow.core.services.models import Service


class ServiceDict(TypedDict):
    id: int
    integration_id: int
    type: str


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
class UpdatedService:
    service: Service
    original_service_values: dict[str, any]
    new_service_values: dict[str, any]


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
