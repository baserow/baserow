from typing import Optional, Union

from baserow.contrib.database.fields.formula_visitors import (  # noqa: F401
    FIELD_ID_RE,
    BaserowFormulaReplaceFieldReferences,
    FieldIDExtractingVisitor,
    extract_field_id_dependencies,
    replace_field_id_references,
)
from baserow.core.cache import local_cache
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.parser.exceptions import BaserowFormulaException

# Backwards-compat alias for existing premium imports/tests.
AIFieldIDExtractingVisitor = FieldIDExtractingVisitor


def get_table_field_ids(table_id: int) -> set[int]:
    """
    Returns the ids of the non-trashed fields in the given table, cached per
    request/task so validating many AI fields doesn't repeat the query. The cache
    is invalidated by `table_schema_changed` (see receivers.py).
    """

    from baserow.contrib.database.fields.models import Field

    return local_cache.get(
        f"ai_prompt_table_field_ids_{table_id}",
        lambda: set(
            Field.objects.filter(table_id=table_id, trashed=False).values_list(
                "id", flat=True
            )
        ),
    )


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
