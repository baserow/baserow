from typing import Any

from loguru import logger

from baserow.contrib.agent.registries import agent_data_provider_type_registry
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import (
    BaserowFormulaException,
    BaserowFormulaObject,
    get_parse_tree_for_formula,
)
from baserow.core.formula.registries import DataProviderTypeRegistry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.services.formula_importer import BaserowFormulaImporter


class AgentFormulaImporter(BaserowFormulaImporter):
    """Updates the paths of an agent formula's `get()` calls to imported ids."""

    def get_data_provider_type_registry(self) -> DataProviderTypeRegistry:
        """
        :return: The registry the agent's formulas name their providers in.
        """

        return agent_data_provider_type_registry


def import_formula(
    formula: str | BaserowFormulaObject, id_mapping: dict[str, Any], **kwargs: Any
) -> BaserowFormulaObject:
    """
    Remap the ids an agent formula references, like the fields of a row trigger's
    table, when the agent is imported. A formula that can't be parsed or names an
    unknown provider was invalid before the import, so it is kept as it is rather
    than stopping the import.

    :param formula: The formula to import.
    :param id_mapping: The export-to-import id map.
    :param kwargs: Passed to each data provider's `import_path`, such as the
        imported `service` of a trigger.
    :return: The imported formula.
    """

    formula = BaserowFormulaObject.to_formula(formula)
    if formula["mode"] == BASEROW_FORMULA_MODE_RAW or not formula["formula"]:
        return formula
    try:
        tree = get_parse_tree_for_formula(formula["formula"])
        imported = AgentFormulaImporter(id_mapping, **kwargs).visit(tree)
    except (
        BaserowFormulaException,
        RecursionError,
        InstanceTypeDoesNotExist,
        ValueError,
    ) as exc:
        logger.warning(
            "Skipping the import of an invalid formula {!r}: {}",
            formula["formula"],
            exc,
        )
        return formula
    if imported == formula["formula"]:
        return formula
    return {**formula, "formula": imported}
