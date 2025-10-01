from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel


class DatabaseItemCreate(BaseModel):
    """Base model for creating a new database (no ID)."""

    name: str = Field(...)


class DatabaseItem(DatabaseItemCreate):
    """Model for an existing database (with ID)."""

    id: int = Field(...)
