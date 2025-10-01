from dataclasses import dataclass
from typing import Any, Dict, Optional

OPTIONAL_FIELDS = [
    "subtitle",
    "description",
    "metadata",
    "created_on",
    "updated_on",
]


@dataclass
class SearchResult:
    """
    Represents a single search result item from workspace search.
    """

    type: str
    id: int
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_on: Optional[str] = None
    updated_on: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""

        result = {
            "type": self.type,
            "id": self.id,
            "title": self.title,
        }

        for field in OPTIONAL_FIELDS:
            value = getattr(self, field)
            if value is not None:
                result[field] = value

        return result


@dataclass
class SearchContext:
    """
    Context information for search operations.
    """

    query: str
    limit: int = 20
    offset: int = 0
