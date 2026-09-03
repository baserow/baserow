"""
Unit tests for the formula validation tool used by the formula sub-agent.

The contract that matters is the exception *class*: pydantic-ai turns only
``ModelRetry`` into a retry prompt, so any other exception escaping this tool
aborts the user's entire turn instead of letting the agent fix its formula.
"""

from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry
from pydantic_ai.messages import RetryPromptPart, ToolCallPart, ToolReturnPart

from baserow_enterprise.assistant.tools.database.agents import (
    GET_FORMULA_TYPE_TOOL_NAME,
    FormulaGenerationResult,
    _type_mismatch_hint,
    _verdict_must_be_backed_by_validation,
    get_formula_type_tool,
)


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula,conversion",
    [
        ("day(field('Customer'))", "todate"),
        ("upper(field('Amount'))", "totext"),
    ],
    ids=["text-into-date-slot", "number-into-text-slot"],
)
def test_type_mismatch_rejection_carries_a_conversion_hint(
    formula_env, formula, conversion
):
    """Pins the _USABLE_TYPES regex to the compiler wording in ast/tree.py."""

    validate, table = formula_env

    with pytest.raises(ModelRetry) as exc_info:
        validate(table.id, "Broken", formula)

    message = str(exc_info.value)
    assert "argument type mismatch" in message
    assert conversion in message


def test_no_usable_type_hint_says_restructure():
    hint = _type_mismatch_hint(
        "argument number 1 given to function x was of type text "
        "but there are no possible types usable here"
    )
    assert "restructure" in hint


def _tool_call(call_id: str, formula: str) -> ToolCallPart:
    return ToolCallPart(
        tool_name=GET_FORMULA_TYPE_TOOL_NAME,
        args={"table_id": 1, "field_name": "F", "formula": formula},
        tool_call_id=call_id,
    )


def _rejection(call_id: str) -> RetryPromptPart:
    return RetryPromptPart(
        content="Invalid formula",
        tool_name=GET_FORMULA_TYPE_TOOL_NAME,
        tool_call_id=call_id,
    )


def _acceptance(call_id: str) -> ToolReturnPart:
    return ToolReturnPart(
        tool_name=GET_FORMULA_TYPE_TOOL_NAME, content="number", tool_call_id=call_id
    )


def _run_ctx(*parts) -> SimpleNamespace:
    return SimpleNamespace(messages=[SimpleNamespace(parts=list(parts))])


def _verdict(formula: str = "field('Amount') * 2", valid: bool = True):
    return FormulaGenerationResult(
        table_id=1,
        field_name="F",
        formula=formula,
        formula_type="number",
        is_formula_valid=valid,
        error_message="" if valid else "cannot be expressed",
    )


def test_valid_verdict_without_any_tool_call_is_sent_back():
    with pytest.raises(ModelRetry, match="never accepted"):
        _verdict_must_be_backed_by_validation(_run_ctx(), _verdict())


def test_valid_verdict_naming_a_rejected_formula_is_sent_back():
    ctx = _run_ctx(_tool_call("c1", "field('Amount') * 2"), _rejection("c1"))

    with pytest.raises(ModelRetry, match="never accepted"):
        _verdict_must_be_backed_by_validation(ctx, _verdict())


def test_valid_verdict_matches_the_accepted_formula_ignoring_whitespace():
    ctx = _run_ctx(_tool_call("c1", "field('Amount')  *\n2"), _acceptance("c1"))
    output = _verdict("field('Amount') * 2")

    assert _verdict_must_be_backed_by_validation(ctx, output) is output


def test_impossible_verdict_after_one_rejection_is_sent_back():
    ctx = _run_ctx(_tool_call("c1", "day(field('Customer'))"), _rejection("c1"))

    with pytest.raises(ModelRetry, match="materially different"):
        _verdict_must_be_backed_by_validation(ctx, _verdict(valid=False))


def test_impossible_verdict_after_retrying_the_same_formula_is_sent_back():
    ctx = _run_ctx(
        _tool_call("c1", "day( field('Customer') )"),
        _rejection("c1"),
        _tool_call("c2", "day(\nfield('Customer')\n)"),
        _rejection("c2"),
    )

    with pytest.raises(ModelRetry, match="materially different"):
        _verdict_must_be_backed_by_validation(ctx, _verdict(valid=False))


def test_impossible_verdict_backed_by_two_different_rejections_passes():
    ctx = _run_ctx(
        _tool_call("c1", "day(field('Customer'))"),
        _rejection("c1"),
        _tool_call("c2", "todate(field('Customer'), 'YYYY')"),
        _rejection("c2"),
    )
    output = _verdict(valid=False)

    assert _verdict_must_be_backed_by_validation(ctx, output) is output


@pytest.mark.django_db
def test_formula_fixer_contains_generator_failures(data_fixture, monkeypatch):
    """The fixer runs inside another except handler, so it must never raise."""

    from pydantic_ai.exceptions import UnexpectedModelBehavior

    from baserow_enterprise.assistant.deps import ToolHelpers
    from baserow_enterprise.assistant.tools.database import agents as database_agents

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=table, name="Customer", primary=True)

    def raise_retries_exhausted(*args, **kwargs):
        raise UnexpectedModelBehavior("Exceeded maximum output retries (3)")

    monkeypatch.setattr(
        database_agents.formula_generation_agent, "run_sync", raise_retries_exhausted
    )

    tool_helpers = ToolHelpers(lambda x: None, lambda x: None)
    fix_formula = database_agents.make_formula_fixer(user, workspace, tool_helpers)

    assert fix_formula(table, "Total", "field('Missing') *") is None
