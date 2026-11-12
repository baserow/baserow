import pytest
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from baserow_enterprise.assistant.history import (
    UNFINISHED_ANSWER,
    append_turn,
    compact_message_history,
    count_user_prompts,
    unfinished_answer,
)


def _texts(history: bytes) -> list[str]:
    messages = ModelMessagesTypeAdapter.validate_json(history)
    return [part.content for message in messages for part in message.parts]


def test_unfinished_answer_keeps_what_the_user_saw():
    assert unfinished_answer("Adding rows") == f"Adding rows\n\n{UNFINISHED_ANSWER}"
    assert unfinished_answer("") == UNFINISHED_ANSWER


def test_count_user_prompts_counts_prompt_parts_only():
    messages = [
        ModelRequest(parts=[UserPromptPart(content="a"), UserPromptPart(content="b")]),
        ModelResponse(parts=[TextPart(content="x")]),
        ModelRequest(
            parts=[ToolReturnPart(tool_name="t", content="r", tool_call_id="1")]
        ),
    ]

    assert count_user_prompts(messages) == 2


SAVED_TURN = ModelMessagesTypeAdapter.dump_json(
    [
        ModelRequest(parts=[UserPromptPart(content="Hi")]),
        ModelResponse(parts=[TextPart(content="Hello")]),
    ]
)


@pytest.mark.parametrize(
    "history,expected",
    [
        (memoryview(SAVED_TURN), ["Hi", "Hello", "Add a table", "Noted"]),
        (None, ["Add a table", "Noted"]),
        (b"not json", ["Add a table", "Noted"]),
    ],
)
def test_append_turn_extends_a_readable_history_or_replaces_it(history, expected):
    assert _texts(append_turn(history, "Add a table", "Noted")) == expected


def test_an_unfinished_turn_compacts_without_its_unanswered_tool_call():
    unfinished = [
        ModelRequest(parts=[UserPromptPart(content="Add rows")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="create_rows", args={}, tool_call_id="c1")]
        ),
        ModelResponse(parts=[TextPart(content=unfinished_answer("Adding rows"))]),
    ]

    compacted = compact_message_history(unfinished)

    assert [type(message) for message in compacted] == [ModelRequest, ModelResponse]
    assert compacted[-1].parts[0].content == unfinished_answer("Adding rows")
