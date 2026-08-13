"""
Unit tests for the formula validation tool used by the formula sub-agent.

The contract that matters is the exception *class*: pydantic-ai turns only
``ModelRetry`` into a retry prompt, so any other exception escaping this tool
aborts the user's entire turn instead of letting the agent fix its formula.
"""

import pytest
from pydantic_ai import ModelRetry

from baserow_enterprise.assistant.tools.database.agents import get_formula_type_tool


@pytest.fixture
def formula_env(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=table, name="Customer")
    data_fixture.create_number_field(table=table, name="Amount")
    return get_formula_type_tool(user, workspace), table


@pytest.mark.django_db
def test_valid_formula_returns_its_type(formula_env):
    validate, table = formula_env

    assert validate(table.id, "Label", "concat(field('Customer'), '!')") == "text"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula,expected_in_message",
    [
        ("or(true, true, true)", "or"),
        ("{Amount} + 1", "{"),
        ("weekday(field('Amount'))", "weekday"),
        ("field('Nonexistent')", "Nonexistent"),
    ],
    ids=["or-arity", "curly-braces", "unknown-function", "unknown-field"],
)
def test_invalid_formula_asks_the_model_to_retry(
    formula_env, formula, expected_in_message
):
    validate, table = formula_env

    with pytest.raises(ModelRetry) as exc_info:
        validate(table.id, "Broken", formula)

    assert expected_in_message in str(exc_info.value)


@pytest.mark.django_db
def test_rejection_lists_the_available_fields(formula_env):
    validate, table = formula_env

    with pytest.raises(ModelRetry) as exc_info:
        validate(table.id, "Broken", "field('Nonexistent')")

    message = str(exc_info.value)
    assert "Customer" in message
    assert "Amount" in message


@pytest.mark.django_db
def test_unknown_table_asks_the_model_to_retry_with_valid_ids(formula_env):
    validate, table = formula_env

    with pytest.raises(ModelRetry) as exc_info:
        validate(table.id + 999, "Broken", "field('Customer')")

    assert str(table.id) in str(exc_info.value)


@pytest.mark.django_db
def test_table_outside_the_workspace_is_not_leaked(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_table = data_fixture.create_database_table(name="Secret")

    validate = get_formula_type_tool(user, workspace)

    with pytest.raises(ModelRetry):
        validate(other_table.id, "Broken", "field('Customer')")
