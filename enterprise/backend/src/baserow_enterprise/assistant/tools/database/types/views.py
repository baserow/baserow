from pydantic import Field

from baserow.contrib.database.tools.views import (  # noqa: F401
    FormFieldOption,
    ViewItem,
    ViewItemCreate,
    ViewType,
)
from baserow_enterprise.assistant.types import BaseModel

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class GridFieldOption(BaseModel):
    field_id: int = Field(...)
    width: int = Field(
        ...,
        description="The width of the field in the grid view (e.g. 200).",
    )
    hidden: bool = Field(
        ...,
        description="Whether the field is hidden in the grid view.",
    )
