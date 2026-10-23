"""Tests for telling automation formulas from literals and checking them."""

import pytest

from baserow.contrib.automation.tools.formulas import (
    InvalidAutomationFormula,
    check_automation_formula,
    needs_formula,
    wrap_static_string,
)


def test_a_valid_formula_passes():
    check_automation_formula("subject", "get('previous_node.1.0.name')")
    check_automation_formula("subject", "concat('Hi ', get('previous_node.1.0.name'))")


@pytest.mark.parametrize(
    "formula,message",
    [
        ("concat(", "Invalid syntax"),
        ("frobnicate(1)", "Unsupported function 'frobnicate'."),
        ("get('nope.1')", "'nope' is not a data source."),
        ("", "'subject' needs a formula."),
        (
            "$formula: the name",
            "'subject' needs a formula, not a description. Write it in Baserow "
            "formula syntax.",
        ),
        (
            "Hello $formula: the name",
            "'subject' needs a formula, not a description.",
        ),
    ],
)
def test_an_invalid_formula_fails_with_a_message(formula, message):
    with pytest.raises(InvalidAutomationFormula) as exc:
        check_automation_formula("subject", formula)

    assert message in exc.value.error
    assert exc.value.field == "subject"
    assert exc.value.formula == formula


@pytest.mark.parametrize(
    "value,is_formula",
    [
        ("Hello", False),
        ("It's 5 o'clock", False),
        (None, False),
        ("", False),
        ("Hello {{ name }}", True),
        ("concat('a', 'b')", True),
        ("get('previous_node.1.0.name')", True),
        ("$formula: the name", True),
        ("greater_than(1, 2)", True),
    ],
)
def test_formulas_are_told_from_literals(value, is_formula):
    assert needs_formula(value) is is_formula


def test_literals_are_quoted_once():
    assert wrap_static_string("Hello") == "'Hello'"
    assert wrap_static_string("'Hello'") == "'Hello'"
    assert wrap_static_string("Managers' Week") == "'Managers\\' Week'"


def test_service_values_leave_an_invalid_formula_empty():
    from baserow.contrib.automation.tools.types import (
        AutomationFieldValue,
        ServiceValues,
    )

    values = ServiceValues(table_field_ids=lambda table_id: {1})

    assert values.value("subject", "Hello") == "'Hello'"
    assert values.value("subject", "get('previous_node.1.0.name')") == (
        "get('previous_node.1.0.name')"
    )
    assert values.value("body", "$formula: the name") == ""
    assert (
        values.field_mappings(
            7,
            [
                AutomationFieldValue(field_id=1, value="concat("),
                AutomationFieldValue(field_id=2, value="x"),
            ],
        )
        == []
    )
    assert [(exc.field, target) for exc, target in values.invalid] == [
        ("body", {}),
        ("values", {"field_id": 1}),
    ]
    assert values.errors == ["Field 2 is not in table 7, so its value was not set."]


@pytest.mark.parametrize("value", ["Order now (today only)", "if (you can)"])
def test_text_with_a_word_before_a_parenthesis_is_a_literal(value):
    assert needs_formula(value) is False


def test_a_previous_node_path_needs_a_node_id():
    from baserow.contrib.automation.tools.formulas import resolve_node_refs

    with pytest.raises(InvalidAutomationFormula, match="'trigger' is not a node ID"):
        check_automation_formula("row_id", "get('previous_node.trigger.0.id')")

    resolved = resolve_node_refs("get('previous_node.trigger.0.id')", {"trigger": 7})
    assert resolved == "get('previous_node.7.0.id')"
    check_automation_formula("row_id", resolved)
