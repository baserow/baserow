from pydantic import BaseModel, Field


class Row(BaseModel):
    id: int
    order: str


class Table(BaseModel):
    id: int
    order: int
    name: str
    database_id: int


class Field(BaseModel):
    id: int
    table_id: int
    name: str
    order: int
    type: str
    primary: bool
    read_only: bool
    description: str
