from dataclasses import dataclass, field
from typing import Any, Dict, NewType, TypedDict, TypeVar

from baserow.core.integrations.models import Integration


class IntegrationDict(TypedDict):
    id: int
    name: str
    order: int
    type: str


IntegrationDictSubClass = TypeVar("IntegrationDictSubClass", bound="IntegrationDict")

IntegrationSubClass = TypeVar("IntegrationSubClass", bound="Integration")

IntegrationForUpdate = NewType("IntegrationForUpdate", Integration)


@dataclass
class UpdatedIntegration:
    integration: Integration
    original_values: Dict[str, Any]
    new_values: Dict[str, Any]


@dataclass
class IntegrationExport:
    """References collected by the consumers included in one application export."""

    integration_ids: set[int] = field(default_factory=set)
