from uuid import uuid4

import pytest
from pydantic import ValidationError as InputValidationError
from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.action_tools.data_providers import AgentActionDispatchContext
from baserow.contrib.agent.action_tools.inputs import (
    build_input_model,
    validate_action_name,
    validate_inputs,
)


def input_definition(name="value", input_type="string", required=True):
    return {
        "id": str(uuid4()),
        "name": name,
        "type": input_type,
        "description": "A tool input",
        "required": required,
    }


@pytest.mark.parametrize(
    "input_type,value",
    [
        ("string", 1),
        ("email", "not-an-email"),
        ("number", "2"),
        ("number", True),
        ("number", float("inf")),
        ("boolean", "false"),
        ("boolean", 0),
        ("string", None),
    ],
)
def test_tool_inputs_reject_wrong_types_without_coercion(input_type, value):
    model = build_input_model([input_definition(input_type=input_type)])
    with pytest.raises(InputValidationError):
        model.model_validate({"value": value})


@pytest.mark.parametrize("value", [250, 2.5])
def test_number_inputs_keep_the_number_the_model_sent(value):
    model = build_input_model([input_definition(input_type="number")])
    kept = model.model_validate({"value": value}).model_dump(by_alias=True)["value"]
    assert (type(kept), kept) == (type(value), value)
    assert model.model_json_schema()["properties"]["value"]["type"] == "number"


def test_names_starting_like_an_mcp_tool_are_reserved():
    with pytest.raises(ValidationError):
        validate_action_name("mcp12_search")
    assert validate_action_name("mcp_search") == "mcp_search"
    assert validate_inputs([input_definition("mcp12_search")])


def test_input_schema_and_validation_share_required_optional_and_custom_names():
    inputs = [
        input_definition("model_dump"),
        input_definition("_optional", "email", False),
    ]
    model = build_input_model(inputs)
    assert model.model_json_schema()["required"] == ["model_dump"]
    assert set(model.model_json_schema()["properties"]) == {"model_dump", "_optional"}
    assert model.model_validate({"model_dump": "hello"}).model_dump(by_alias=True) == {
        "model_dump": "hello",
        "_optional": None,
    }
    for arguments in ({}, {"model_dump": "hello", "other": "secret"}):
        with pytest.raises(InputValidationError):
            model.model_validate(arguments)


@pytest.mark.parametrize(
    "change",
    [
        {"id": "not-a-uuid"},
        {"name": "hello.world"},
        {"name": ""},
        {"type": "object"},
        {"required": "false"},
        {"description": []},
    ],
)
def test_input_definitions_reject_invalid_contracts(change):
    with pytest.raises(ValidationError):
        validate_inputs([{**input_definition(), **change}])


def test_input_definitions_reject_duplicate_names_and_ids():
    first = input_definition()
    with pytest.raises(ValidationError):
        validate_inputs([first, {**first, "name": "second"}])
    with pytest.raises(ValidationError):
        validate_inputs([first, {**first, "id": str(uuid4())}])
    assert validate_inputs([first]) == [first]


def test_tool_input_context_clone_preserves_values_and_stable_identity():
    input_id = str(uuid4())
    context = AgentActionDispatchContext(tool_inputs={input_id: "Alice"})
    assert context.clone()[f"tool_input.{input_id}"] == "Alice"
