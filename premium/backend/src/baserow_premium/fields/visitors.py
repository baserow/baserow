from typing import Optional, Union

from baserow.contrib.database.fields.formula_visitors import (
    extract_field_id_dependencies,
    get_table_field_ids,
    replace_field_id_references,
)
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.parser.exceptions import BaserowFormulaException

__all__ = [
    "extract_field_id_dependencies",
    "get_ai_prompt_error",
    "get_table_field_ids",
    "replace_field_id_references",
]


def get_ai_prompt_error(
    prompt: Union[str, BaserowFormulaObject], table_id: int
) -> Optional[str]:
    """
    Validates an AI field prompt formula. Returns an error message when the prompt
    cannot be parsed or references a field that does not exist (non-trashed) in the
    given table. Returns None for an empty or valid prompt.
    """

    formula_str = prompt if isinstance(prompt, str) else prompt["formula"]
    if not formula_str:
        return None

    try:
        referenced_ids = extract_field_id_dependencies(formula_str)
    except BaserowFormulaException:
        return "The prompt formula could not be parsed."

    if referenced_ids and referenced_ids - get_table_field_ids(table_id):
        return "The prompt references a field that no longer exists."

    return None
