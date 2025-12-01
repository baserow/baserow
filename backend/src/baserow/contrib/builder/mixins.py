from baserow.contrib.builder.formula_property_extractor import FormulaFieldVisitor
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.registry import InstanceWithFormulaMixin
from baserow.core.utils import merge_dicts_no_duplicates


class BuilderInstanceWithFormulaMixin(InstanceWithFormulaMixin):
    def extract_properties(self, instance, **kwargs):
        result = {}

        for formula in self.formula_generator(instance):
            # Figure out what our formula string is.
            formula_str = BaserowFormulaObject.to_formula(formula)["formula"]

            if not formula_str:
                continue

            try:
                tree = get_parse_tree_for_formula(formula_str)
            except BaserowFormulaSyntaxError:
                continue

            result = merge_dicts_no_duplicates(
                result, FormulaFieldVisitor(**kwargs).visit(tree)
            )

        return result
