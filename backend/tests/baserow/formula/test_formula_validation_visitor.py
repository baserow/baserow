import pytest

from baserow.core.formula.parser.formula_validation_visitor import (
    BaserowFormulaValidationVisitor,
)
from baserow.core.formula.parser.parser import get_parse_tree_for_formula
from baserow.core.formula.registries import (
    DataProviderType,
    DataProviderTypeRegistry,
    formula_runtime_function_registry,
)
from baserow.test_utils.helpers import load_test_cases

TEST_DATA = load_test_cases("formula_visitor_cases")

VALID_FORMULA_VALIDATION_TESTS = TEST_DATA["VALID_FORMULA_VALIDATION_TESTS"]
INVALID_FORMULA_VALIDATION_TESTS = TEST_DATA["INVALID_FORMULA_VALIDATION_TESTS"]


class TestDataProviderType(DataProviderType):
    type = "test_data_provider"

    def get_data_chunk(self, dispatch_context, path):
        return None


# Create registry once at module level to avoid concurrent registration issues
_test_data_provider_registry = DataProviderTypeRegistry()
_test_data_provider_registry.register(TestDataProviderType())


@pytest.mark.django_db
@pytest.mark.parametrize("test_data", VALID_FORMULA_VALIDATION_TESTS)
def test_valid_formulas(test_data):
    formula = test_data["formula"]

    tree = get_parse_tree_for_formula(formula)
    try:
        BaserowFormulaValidationVisitor(
            formula_runtime_function_registry,
            data_provider_type_registry=_test_data_provider_registry,
        ).visit(tree)
    except Exception as e:
        pytest.fail(f"Validation raised an unexpected exception: {e}")


@pytest.mark.django_db
@pytest.mark.parametrize("test_data", INVALID_FORMULA_VALIDATION_TESTS)
def test_invalid_formulas(test_data):
    formula = test_data["formula"]
    expected_error = test_data["backend_error"]

    tree = get_parse_tree_for_formula(formula)

    with pytest.raises(Exception) as exc_info:
        BaserowFormulaValidationVisitor(
            formula_runtime_function_registry,
            data_provider_type_registry=_test_data_provider_registry,
        ).visit(tree)
    if expected_error:
        assert expected_error in str(exc_info)
