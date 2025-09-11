from typing import Literal
from pydantic import BaseModel, Field


class DatabaseArchitectToolArgsSchema(BaseModel):
    instructions: str = Field(
        description=("The user's instructions for the database schema design.")
    )


class BaseFieldType(BaseModel):
    name: str
    type: str


class TextFieldType(BaseFieldType):
    type: str = "text"


class LongTextFieldType(BaseFieldType):
    type: str = "long_text"


class NumberFieldType(BaseFieldType):
    type: str = "number"


class DateFieldType(BaseFieldType):
    type: str = "date"
    include_time: bool = False


class BooleanFieldType(BaseFieldType):
    type: str = "boolean"


class LinkRowFieldType(BaseFieldType):
    type: str = "link_row"
    linked_table_name: str = Field(
        description="The name of the table being linked to. Only link already created tables. A reverse link will be created automatically."
    )
    multiple: bool = False


ColorName = Literal[
    "blue",
    "green",
    "cyan",
    "orange",
    "yellow",
    "red",
    "brown",
    "purple",
    "pink",
    "gray",
]


class SelectOptions(BaseModel):
    value: str
    color: ColorName


class SingleSelectFieldType(BaseFieldType):
    type: str = "single_select"
    options: list[str] = []


class MultipleSelectFieldType(BaseFieldType):
    type: str = "multiple_select"
    options: list[str] = []


class TableSchema(BaseModel):
    name: str
    primary_field: TextFieldType
    fields: list[
        TextFieldType
        | LongTextFieldType
        | NumberFieldType
        | DateFieldType
        | BooleanFieldType
        | LinkRowFieldType
        | SingleSelectFieldType
        | MultipleSelectFieldType
    ]
