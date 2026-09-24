"""
Unit tests for the formula validation tool used by the formula sub-agent.

The contract that matters is the exception *class*: pydantic-ai turns only
``ModelRetry`` into a retry prompt, so any other exception escaping this tool
aborts the user's entire turn instead of letting the agent fix its formula.
"""

from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry
from pydantic_ai.messages import (
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel

from baserow_enterprise.assistant import model_profiles
from baserow_enterprise.assistant.tools.database import agents as database_agents
from baserow_enterprise.assistant.tools.database.agents import (
    GET_FORMULA_TYPE_TOOL_NAME,
    FormulaGenerationResult,
    _type_mismatch_hint,
    _verdict_must_be_backed_by_validation,
    get_formula_type_tool,
)

from .utils import create_fake_tool_helpers


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


def test_valid_verdict_matches_the_accepted_formula_and_field():
    ctx = _run_ctx(_tool_call("c1", "field('Amount') * 2"), _acceptance("c1"))
    output = _verdict()

    assert _verdict_must_be_backed_by_validation(ctx, output) is output


@pytest.mark.parametrize("changed_field", ["table_id", "field_name"])
def test_valid_verdict_must_match_the_validated_field(changed_field):
    ctx = _run_ctx(_tool_call("c1", "field('Amount') * 2"), _acceptance("c1"))
    output = _verdict()
    if changed_field == "table_id":
        output.table_id = 2
    else:
        output.field_name = "Amount"

    with pytest.raises(ModelRetry, match="never accepted"):
        _verdict_must_be_backed_by_validation(ctx, output)


@pytest.mark.parametrize(
    "validated_formula,returned_formula",
    [
        ("field('Amount')  *\n2", "field('Amount') * 2"),
        ("field('Two  Spaces')", "field('Two Spaces')"),
        ("'two  spaces'", "'two spaces'"),
        ('"two  spaces"', '"two spaces"'),
    ],
    ids=["formatting", "field-reference", "single-quoted", "double-quoted"],
)
def test_valid_verdict_requires_the_exact_validated_formula(
    validated_formula, returned_formula
):
    ctx = _run_ctx(_tool_call("c1", validated_formula), _acceptance("c1"))

    with pytest.raises(ModelRetry, match="never accepted"):
        _verdict_must_be_backed_by_validation(ctx, _verdict(returned_formula))


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


@pytest.mark.parametrize("raw_table_id", [1, "1.0"])
def test_formula_generation_reuses_the_request_profile_and_owns_its_model(
    monkeypatch, raw_table_id
):
    lifecycle = []
    requested_models = []
    observed_settings = []

    def get_formula_type(table_id: int, field_name: str, formula: str) -> str:
        assert (table_id, field_name, formula) == (1, "F", "field('Amount') * 2")
        return "number"

    def respond(messages, info):
        observed_settings.append(info.model_settings)
        if any(
            isinstance(part, ToolReturnPart)
            for message in messages
            for part in message.parts
        ):
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args=_verdict().model_dump(),
                        tool_call_id="result",
                    )
                ]
            )
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=GET_FORMULA_TYPE_TOOL_NAME,
                    args={
                        "table_id": raw_table_id,
                        "field_name": "F",
                        "formula": "field('Amount') * 2",
                    },
                    tool_call_id="validation",
                )
            ]
        )

    class LifecycleModel(FunctionModel):
        async def __aenter__(self):
            lifecycle.append("entered")
            return await super().__aenter__()

        async def __aexit__(self, *args):
            lifecycle.append("exited")
            return await super().__aexit__(*args)

    model = LifecycleModel(respond)

    def create_model(model_string):
        requested_models.append(model_string)
        return model

    monkeypatch.setattr(model_profiles, "RetryingModel", create_model)
    monkeypatch.setattr(
        database_agents,
        "get_formula_type_tool",
        lambda user, workspace: get_formula_type,
    )
    profile = model_profiles.ResolvedAssistantModelProfile(
        model_string="openai:gpt-4.1-mini",
        source="explicit",
        workspace=None,
        database_model=None,
    )

    result = database_agents.run_formula_generation(None, None, "Generate", profile)

    assert result.output == _verdict()
    assert requested_models == [profile.model_string]
    assert observed_settings == [profile.get_settings(model_profiles.UTILITY)] * 2
    assert lifecycle == ["entered", "exited"]
    validation_call = next(
        part
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolCallPart)
        and part.tool_name == GET_FORMULA_TYPE_TOOL_NAME
    )
    assert validation_call.args_as_dict()["table_id"] == raw_table_id


@pytest.mark.django_db
def test_formula_fixer_contains_generator_failures(data_fixture, monkeypatch):
    """The fixer runs inside another except handler, so it must never raise."""

    from pydantic_ai.exceptions import UnexpectedModelBehavior

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=table, name="Customer", primary=True)

    def raise_retries_exhausted(*args, **kwargs):
        raise UnexpectedModelBehavior("Exceeded maximum output retries (3)")

    monkeypatch.setattr(
        database_agents, "run_agent_sync_with_model", raise_retries_exhausted
    )

    tool_helpers = create_fake_tool_helpers()
    fix_formula = database_agents.make_formula_fixer(user, workspace, tool_helpers)

    assert fix_formula(table, "Total", "field('Missing') *") is None
