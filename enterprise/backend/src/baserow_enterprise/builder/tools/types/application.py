"""
Builder application type models.

Defines ``BuilderCreate`` for creating application builders.
"""

from pydantic import Field

from baserow_enterprise.builder.tools.themes import ThemeName
from baserow_enterprise.tools.types import BaseModel


class BuilderCreate(BaseModel):
    """An application builder to create."""

    name: str = Field(..., description="The name of the application builder.")
    theme: ThemeName | None = Field(
        default=None,
        description="The theme to start with. The default is 'baserow'.",
    )
