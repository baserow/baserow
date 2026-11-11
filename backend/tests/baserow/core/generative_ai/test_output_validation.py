import json
from types import SimpleNamespace

import pytest
from pydantic_ai import Agent, DeferredToolRequests, ModelRetry
from pydantic_ai.messages import ModelResponse, RetryPromptPart, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.tools import ToolDefinition

from baserow.core.generative_ai.output_validation import (
    get_printed_tool_call,
    validate_tool_call_output,
)


@pytest.fixture
def ctx():
    tools = {
        "create_tables": ToolDefinition(name="create_tables"),
        "final_result": ToolDefinition(name="final_result", kind="output"),
    }
    return SimpleNamespace(tool_manager=SimpleNamespace(get_tool_def=tools.get))


@pytest.mark.parametrize(
    "answer",
    [
        '{"name":"create_tables","arguments":{}}',
        ' \n{"arguments":{"tables":[]},"name":"create_tables"}\n ',
        json.dumps({"arguments": {"description": "x" * 300}, "name": "create_tables"}),
    ],
)
def test_a_whole_answer_calling_an_offered_tool_is_retried(ctx, answer):
    with pytest.raises(ModelRetry, match="Use the tool interface") as error:
        validate_tool_call_output(ctx, answer)

    # The answer is already in model history; don't duplicate its arguments.
    assert "description" not in str(error.value)
    assert "Do not repeat changes that already succeeded" in str(error.value)
    assert get_printed_tool_call(ctx, answer) == (
        "create_tables",
        json.loads(answer)["arguments"],
    )


@pytest.mark.parametrize(
    "answer",
    [
        "The tables already exist.",
        'Example: {"name":"create_tables","arguments":{}}',
        '```json\n{"name":"create_tables","arguments":{}}\n```',
        '{"name":"create_tables","arguments":{}} is an example.',
        '{"name":"another_tool","arguments":{}}',
        '{"name":"final_result","arguments":{}}',
        '{"name":"create_tables","arguments":{},"description":"Example"}',
        '{"name":"create_tables"}',
        '{"name":42,"arguments":{}}',
        '{"name":"create_tables","arguments":[]}',
        '{"name":"create_tables","arguments":"{}"}',
        '{"name":"create_tables","arguments":null}',
        '[{"name":"create_tables","arguments":{}}]',
        '{"name":"create_tables","arguments":',
        '"create_tables"',
        "null",
    ],
)
def test_examples_and_unrelated_or_malformed_json_pass_through(ctx, answer):
    assert validate_tool_call_output(ctx, answer) == answer


@pytest.mark.parametrize(
    "ctx", [None, SimpleNamespace(), SimpleNamespace(tool_manager=None)]
)
def test_without_offered_tools_json_is_not_treated_as_a_call(ctx):
    answer = '{"name":"create_tables","arguments":{}}'

    assert validate_tool_call_output(ctx, answer) == answer


def test_deferred_tool_requests_are_not_text(ctx):
    deferred = DeferredToolRequests()

    assert validate_tool_call_output(ctx, deferred) is deferred


@pytest.mark.parametrize("kind", ["external", "unapproved"])
def test_printing_a_call_does_not_bypass_deferred_tools(kind):
    tool = ToolDefinition(name="create_tables", kind=kind)
    ctx = SimpleNamespace(
        tool_manager=SimpleNamespace(get_tool_def={tool.name: tool}.get)
    )

    with pytest.raises(ModelRetry, match="Use the tool interface"):
        validate_tool_call_output(ctx, '{"name":"create_tables","arguments":{}}')


def test_the_model_must_issue_a_real_call_after_printing_tool_json():
    mutations = []
    retries = []
    responses = iter(
        [
            TextPart('{"name":"create_tables","arguments":{"name":"Projects"}}'),
            ToolCallPart("create_tables", {"name": "Projects"}),
            TextPart("Created Projects."),
        ]
    )

    def create_tables(name: str) -> str:
        mutations.append(name)
        return name

    def model(messages, info):
        retries.extend(
            part.content
            for part in messages[-1].parts
            if isinstance(part, RetryPromptPart)
        )
        return ModelResponse(parts=[next(responses)])

    agent = Agent(tools=[create_tables], retries={"output": 2})
    agent.output_validator(validate_tool_call_output)

    result = agent.run_sync("Create Projects.", model=FunctionModel(model))

    assert result.output == "Created Projects."
    assert mutations == ["Projects"]
    assert len(retries) == 1
    assert "Use the tool interface" in retries[0]
