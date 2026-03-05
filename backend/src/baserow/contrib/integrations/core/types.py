from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from django.db.models import QuerySet

if TYPE_CHECKING:
    from baserow.contrib.integrations.core.models import CorePeriodicService


@dataclass
class CorePeriodicServiceDueResult:
    services_due: QuerySet["CorePeriodicService"]
    services_dispatched: List["CorePeriodicService"]
