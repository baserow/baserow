import pytest

from baserow.contrib.dashboard.filters.options import get_table_field_path
from baserow.contrib.dashboard.filters.references import (
    get_referenced_dashboard_filters,
)
from baserow.contrib.dashboard.filters.runtime import get_dashboard_filter_path
from baserow.contrib.dashboard.formula_importer import import_formula
from baserow.core.formula import resolve_formula
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BaserowFormulaObject


@pytest.mark.parametrize(
    "expression,path",
    [
        ("get('dashboard_filter.17')", ["17"]),
        ("get( 'dashboard_filter.17' )", ["17"]),
        ("get(('dashboard_filter.17'))", ["17"]),
        (' (GET("dashboard_filter.17")) ', ["17"]),
        ("get('dashboard_filter[17]')", ["17"]),
        ("get('dashboard_filter.17[0]')", ["17", "0"]),
        ("get( ('dashboard_filter[17][*]') )", ["17", "*"]),
        ("get('dashboard_filter[ 17 ][ * ]')", ["17", "*"]),
    ],
)
def test_dashboard_filter_reference_semantics_are_consistent(expression, path):
    formula = BaserowFormulaObject.create(expression, "advanced")
    assert get_dashboard_filter_path(formula) == path
    assert get_referenced_dashboard_filters(formula) == {17}

    imported = import_formula(formula, {"dashboard_filters": {17: 42}})
    assert get_dashboard_filter_path(imported) == ["42", *path[1:]]
    assert get_referenced_dashboard_filters(imported) == {42}

    missing = import_formula(formula, {})
    assert get_referenced_dashboard_filters(missing) == set()
    assert resolve_formula(missing, formula_runtime_function_registry, {}) is None


@pytest.mark.parametrize(
    "expression",
    [
        "get('table.10.*.field_20')",
        "get( 'table.10.*.field_20' )",
        "get(('table.10.*.field_20'))",
        "(get('table[10][*].field_20'))",
    ],
)
def test_option_table_references_use_the_same_import_contract(expression):
    formula = BaserowFormulaObject.create(expression, "advanced")
    assert get_table_field_path(formula) == (10, "field_20")
    imported = import_formula(
        formula,
        {"database_tables": {10: 30}, "database_fields": {20: 40}},
    )
    assert get_table_field_path(imported) == (30, "field_40")


def test_calculated_references_remap_without_inheriting_a_control_operator():
    formula = BaserowFormulaObject.create(
        "concat(get( 'dashboard_filter[17][0]' ), get(('dashboard_filter.18')))",
        "advanced",
    )
    assert get_dashboard_filter_path(formula) is None
    assert get_referenced_dashboard_filters(formula) == {17, 18}
    imported = import_formula(formula, {"dashboard_filters": {17: 42}})
    assert get_dashboard_filter_path(imported) is None
    assert get_referenced_dashboard_filters(imported) == {42}
    assert imported["formula"] == "concat(get('dashboard_filter.42.0'),null())"


def test_raw_text_is_not_a_formula_reference():
    formula = BaserowFormulaObject.create("get('dashboard_filter.17')", "raw")
    assert get_dashboard_filter_path(formula) is None
    assert get_referenced_dashboard_filters(formula) == set()
    assert import_formula(formula, {}) == formula


@pytest.mark.parametrize(
    "reference", ['dashboard_filter["17"]["*"]', "dashboard_filter[17.0]"]
)
def test_dashboard_references_reject_non_numeric_property_keys(reference):
    formula = BaserowFormulaObject.create(f"get('{reference}')", "advanced")
    with pytest.raises(BaserowFormulaSyntaxError):
        get_dashboard_filter_path(formula)
