"""
Builder user source type models.

Defines ``UserSourceSetup`` for creating user sources with their backing
tables and authentication providers.
"""

from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from baserow.contrib.builder.tools.types.limits import MAX_NESTED_ITEMS
from baserow.core.tools.types import BaseModel

_DEFAULT_ROLES = ["Admin", "Member", "Viewer"]

# The name column of the user source model is 255 characters long.
UserSourceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class UserSourceSetup(BaseModel):
    """
    Set up a user source for the application.

    Exactly one of ``table_id`` or ``database_id`` must be provided.
    """

    name: UserSourceName = Field(..., description="Name for the user source.")

    table_id: int | None = Field(
        None, description="Existing table ID to use as user source."
    )
    database_id: int | None = Field(
        None, description="Database ID to create a new users table in."
    )

    roles: list[str] | None = Field(
        None,
        max_length=MAX_NESTED_ITEMS,
        description=(
            "Role names for the SingleSelect role field. "
            'Defaults to ["Admin", "Member", "Viewer"]. '
            "Only used when creating a new table."
        ),
    )

    @model_validator(mode="after")
    def _check_table_or_database(self):
        if not self.table_id and not self.database_id:
            raise ValueError("One of 'table_id' or 'database_id' is required.")
        if self.table_id and self.database_id:
            raise ValueError(
                "Only one of 'table_id' or 'database_id' can be provided, not both."
            )
        return self

    def get_roles(self) -> list[str]:
        """Return the roles to use, falling back to defaults."""
        return self.roles or list(_DEFAULT_ROLES)
