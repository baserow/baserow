from typing import TypedDict

from baserow.core.formula.types import BaserowFormulaObject


class FieldMappingValues(TypedDict):
    """One field mapping of an upsert row service, as its update takes it."""

    field_id: int
    enabled: bool
    value: BaserowFormulaObject
