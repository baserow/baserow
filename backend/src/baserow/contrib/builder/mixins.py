from baserow.contrib.builder.formula_property_extractor import FormulaFieldVisitor
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW, BaserowFormulaObject
from baserow.core.registry import InstanceWithFormulaMixin
from baserow.core.utils import merge_dicts_no_duplicates


class BuilderInstanceWithFormulaMixin(InstanceWithFormulaMixin):
    def extract_properties(self, instance, **kwargs):
        result = {}

        for formula in self.formula_generator(instance):
            # Figure out what our formula string is.
            formula_object = BaserowFormulaObject.to_formula(formula)
            formula_str = formula_object["formula"]

            # A raw formula is plain text, not something to parse: it can't
            # reference any property.
            is_raw = formula_object.get("mode") == BASEROW_FORMULA_MODE_RAW
            if not formula_str or is_raw:
                continue

            try:
                tree = get_parse_tree_for_formula(formula_str)
            except BaserowFormulaSyntaxError:
                continue

            result = merge_dicts_no_duplicates(
                result, FormulaFieldVisitor(**kwargs).visit(tree)
            )

        return result
