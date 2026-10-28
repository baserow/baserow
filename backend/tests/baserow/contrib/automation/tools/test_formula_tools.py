"""Tests for telling automation formulas from literals and checking them."""

import re

import pytest

from baserow.contrib.automation.tools.formulas import (
    InvalidAutomationFormula,
    check_automation_formula,
    check_output_paths,
    needs_formula,
    resolve_node_refs,
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


@pytest.mark.parametrize(
    "value",
    ["Order now (today only)", "if (you can)", "Call me (concat ('a', 'b'))"],
)
def test_text_with_a_word_before_a_parenthesis_is_a_literal(value):
    assert needs_formula(value) is False


def test_a_previous_node_path_needs_a_node_id():
    from baserow.contrib.automation.tools.formulas import resolve_node_refs

    with pytest.raises(InvalidAutomationFormula, match="'trigger' is not a node ID"):
        check_automation_formula("row_id", "get('previous_node.trigger.0.id')")

    resolved = resolve_node_refs("get('previous_node.trigger.0.id')", {"trigger": 7})
    assert resolved == "get('previous_node.7.0.id')"
    check_automation_formula("row_id", resolved)


# A rows trigger's output, as output_schema gives it.
ROWS_OUTPUT = {
    "formula_path": "previous_node.7.0",
    "properties": {
        "id": {"title": "Id", "type": "number"},
        "field_3": {
            "title": "Priority",
            "type": "object",
            "properties": {
                "id": {"title": "id", "type": "number"},
                "value": {"title": "value", "type": "string"},
            },
        },
        "field_4": {
            "title": "Tags",
            "type": "array",
            "items": {
                "value": {"title": "value", "type": "string"},
            },
        },
    },
}


def _outputs(node_id):
    return ROWS_OUTPUT if node_id == 7 else None


@pytest.mark.parametrize(
    "formula",
    [
        "get('previous_node.7')",
        "get('previous_node.7.0')",
        "get('previous_node.7.0.id')",
        "get('previous_node.7.*.field_3.value')",
        "equal(get('previous_node.7.0.field_3.value'), 'High')",
        "get('previous_node.7.0.field_4.0.value')",
        "get('previous_node.7.0.field_4.*')",
        "get('previous_node.7.0.Priority')",
        "get('previous_node.7.0.Priority.value')",
    ],
)
def test_a_path_the_node_outputs_passes(formula):
    check_output_paths("condition", formula, _outputs)


@pytest.mark.parametrize(
    "formula,message",
    [
        (
            "get('previous_node.7.Priority') = 'High'",
            "'previous_node.7.Priority' is not an output of node 7. Its outputs: "
            "previous_node.7.0.id (Id), previous_node.7.0.field_3 (Priority), "
            "previous_node.7.0.field_4 (Tags).",
        ),
        ("get('previous_node.7.field_3')", "is not an output of node 7"),
        ("get('previous_node.7.0.Id')", "is not an output of node 7"),
        ("get('previous_node.7.0.Priority.Value')", "is not an output of node 7"),
        ("get('previous_node.7.0.id.value')", "is not an output of node 7"),
        ("get('previous_node.7.0.field_4.value')", "is not an output of node 7"),
        (
            "get('previous_node.8.0.id')",
            "Node 8 is not in this workflow, so 'previous_node.8.0.id' can't be read.",
        ),
    ],
)
def test_a_path_the_node_does_not_output_fails(formula, message):
    with pytest.raises(InvalidAutomationFormula, match=re.escape(message)):
        check_output_paths("condition", formula, _outputs)


def test_a_node_with_an_unknown_output_takes_any_path():
    check_output_paths(
        "subject",
        "get('previous_node.9.anything')",
        lambda node_id: {"formula_path": "previous_node.9", "properties": {}},
    )


def test_previous_node_in_text_is_not_a_node_path():
    formula = "concat('Copied from previous_node.orders', get('previous_node.o.0.id'))"

    assert resolve_node_refs(formula, {"orders": 4, "o": 5}) == (
        "concat('Copied from previous_node.orders', get('previous_node.5.0.id'))"
    )
    check_automation_formula("subject", "concat('from previous_node.orders', 'x')")


@pytest.mark.parametrize(
    "value", ["concat ('Hello ', 'world')", "get ('previous_node.1.0.id')"]
)
def test_a_value_that_is_one_call_with_a_space_is_a_formula(value):
    assert needs_formula(value) is True


def test_formula_text_inside_a_string_literal_is_text():
    quoted_path = """concat("get('previous_node.999999.0.id')", '!')"""
    check_automation_formula("subject", quoted_path)
    check_output_paths("subject", quoted_path, _outputs)
    check_automation_formula("subject", "concat('Send $formula: as text', '!')")

    formula = """concat("get('previous_node.o.0.id')", get('previous_node.o.0.id'))"""
    assert resolve_node_refs(formula, {"o": 5}) == (
        """concat("get('previous_node.o.0.id')", get('previous_node.5.0.id'))"""
    )


def test_a_quote_escaped_in_a_string_literal_doesnt_end_it():
    formula = "concat('it\\'s get(\\'previous_node.x', get('previous_node.x.0.id'))"

    assert resolve_node_refs(formula, {"x": 7}) == (
        "concat('it\\'s get(\\'previous_node.x', get('previous_node.7.0.id'))"
    )
