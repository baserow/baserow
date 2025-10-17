from typing import Dict, Union

from baserow.contrib.builder.data_providers.registries import (
    builder_data_provider_type_registry,
)
from baserow.core.formula import BaserowFormulaObject, get_parse_tree_for_formula
from baserow.core.services.formula_importer import BaserowFormulaImporter


class BuilderFormulaImporter(BaserowFormulaImporter):
    """
    This visitor is used to import formulas in the builder services. It updates the
    paths of the `get()` function calls to reflect the new IDs of the data sources,
    fields, and other objects referenced in the formula.
    """

    def get_data_provider_type_registry(self):
        return builder_data_provider_type_registry


def import_formula(
    formula: Union[str, BaserowFormulaObject], id_mapping: Dict[str, str], **kwargs
) -> str:
    """
    When a formula is used in a service, it must be migrated when we import it because
    it could contain IDs referencing other objects. For example, the formula
    `get('data_source.2.field_25)` references the data source with ID `2`
    and the field with Id `25`.
    In order to update the Id a special process must be applied:

    ```
    from baserow.contrib.builder.formula_importer import import_formula
    ...

    # Later in your code
    serialized_values["property_with_formula"] = import_formula(
                    serialized_values["property_with_formula"], id_mapping
                )
    ```

    :param formula: The formula to import (can be a string or BaserowFormulaObject dict)
    :param id_mapping: The Id map between old and new instances used during import.
    :param kwargs: Sometimes more parameters are needed by the import formula process.
      Extra kwargs are then passed to the underlying migration process.
    :return: The updated formula (same type as input - string or object).
    """

    # Figure out what our formula string is.
    formula_str = formula if isinstance(formula, str) else formula["formula"]

    if not formula_str:
        return formula_str

    tree = get_parse_tree_for_formula(formula_str)
    return BuilderFormulaImporter(id_mapping, **kwargs).visit(tree)
