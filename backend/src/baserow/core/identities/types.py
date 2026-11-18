from dataclasses import dataclass
from typing import Any

from baserow.core.models import User


@dataclass
class UpdatedIdentity:
    identity: User
    original_values: dict[str, Any]
    new_values: dict[str, Any]
