from typing import Dict, Union

from loguru import logger

from baserow.contrib.database.data_providers.registries import (
    database_data_provider_type_registry,
)
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import (
    BaserowFormulaException,
    BaserowFormulaObject,
    get_parse_tree_for_formula,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.services.formula_importer import BaserowFormulaImporter


class DatabaseFormulaImporter(BaserowFormulaImporter):
    """
    Updates the `get()` paths of a formula stored on a database service, so a
    reference such as `get('row.field_25')` names the imported field instead of
    the one it was written against.
    """

    def get_data_provider_type_registry(self):
        return database_data_provider_type_registry


def import_formula(
    formula: Union[str, BaserowFormulaObject], id_mapping: Dict[str, str], **kwargs
) -> BaserowFormulaObject:
    """
    Migrates a formula stored on a button field's action so its references point
    at the imported objects.

    :param formula: The formula to import, as a string or a formula object.
    :param id_mapping: The id map between the old and the new instances.
    :param kwargs: Extra context passed on to the underlying visitor.
    :return: The updated formula object.
    """

    formula = BaserowFormulaObject.to_formula(formula)

    if formula["mode"] == BASEROW_FORMULA_MODE_RAW or not formula["formula"]:
        return formula

    try:
        tree = get_parse_tree_for_formula(formula["formula"])
        new_formula = DatabaseFormulaImporter(id_mapping, **kwargs).visit(tree)
    except (BaserowFormulaException, InstanceTypeDoesNotExist) as exc:
        # Unparseable, or naming a data provider this module doesn't have: keep
        # the formula as it is so the import succeeds. Logged because the visit
        # stops at the first bad `get()`, leaving earlier references unremapped.
        logger.warning(
            f"Could not remap the formula {formula['formula']}, keeping it as "
            f"it is. Reason: {type(exc).__name__}: {exc}"
        )
        return formula

    if new_formula != formula["formula"]:
        # Copied so the caller's formula object isn't mutated.
        formula = dict(formula)
        formula["formula"] = new_formula

    return formula
