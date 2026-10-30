from unittest.mock import Mock

import pytest
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from baserow.core.chat_runs.steps import ChatRunSteps


def call(call_id, name="create_rows", arguments=None, valid=True):
    return FunctionToolCallEvent(
        ToolCallPart(name, arguments or {}, call_id), args_valid=valid
    )


def result(call_id, content=None, facts=None, **kwargs):
    return FunctionToolResultEvent(
        ToolReturnPart("create_rows", content, call_id, metadata=facts, **kwargs)
    )


def describe(name, arguments):
    return {
        "presentation_type": name,
        "changes_data": name == "create_rows",
        "input": {"requested_count": len(arguments["rows"])}
        if "rows" in arguments
        else {},
    }


def test_steps_keep_call_order_and_distinct_ids_when_provider_ids_are_reused():
    journal = Mock()
    steps = ChatRunSteps(journal, describe)
    steps.on_event(call("one", arguments={"rows": [{"secret": "not displayed"}]}))
    steps.on_event(call("two"))
    steps.on_event(result("two", content={"errors": []}, facts={"count": 2}))
    steps.on_event(result("one", facts={"count": 1, "table": "Tasks"}))
    steps.on_event(call("one"))

    saved = steps.finish()
    assert len({step["id"] for step in saved}) == 3
    assert [step["status"] for step in saved] == ["done", "done", "stopped"]
    assert saved[0]["input"] == {"requested_count": 1}
    assert saved[0]["facts"] == {"count": 1, "table": "Tasks"}
    assert saved[1]["facts"] == {"count": 2}
    events = [entry.args[1] for entry in journal.emit.call_args_list]
    assert [step["status"] for step in events] == [
        "running",
        "running",
        "done",
        "done",
        "running",
    ]
    assert "secret" not in str(events)
    assert steps.finish() == saved


@pytest.mark.parametrize(
    "part,status",
    [
        (RetryPromptPart("Try again", tool_call_id="one"), "failed"),
        (ToolReturnPart("tool", {"error": "denied"}, "one"), "failed"),
        (
            ToolReturnPart(
                "tool", {"deleted_field_ids": [], "errors": ["denied"]}, "one"
            ),
            "failed",
        ),
        (
            ToolReturnPart(
                "tool",
                {"updated_fields": [{"id": 1}], "errors": ["other field denied"]},
                "one",
                metadata={"count": 1},
            ),
            "failed",
        ),
        (ToolReturnPart("tool", None, "one", outcome="failed"), "failed"),
        (ToolReturnPart("tool", None, "one", outcome="denied"), "failed"),
        (ToolReturnPart("tool", None, "one", outcome="interrupted"), "stopped"),
    ],
)
def test_failed_or_interrupted_calls_have_no_success_facts(part, status):
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one"))
    steps.on_event(FunctionToolResultEvent(part))
    assert steps.finish()[0]["status"] == status
    assert steps.finish()[0]["facts"] == {}


def test_invalid_call_is_failed_even_without_a_result_and_has_no_input():
    description = Mock(return_value={"input": {"requested_count": 99}})
    steps = ChatRunSteps(Mock(), description)
    steps.on_event(call("one", arguments={"rows": [1]}, valid=False))
    description.assert_called_once_with("create_rows", {})
    saved = steps.finish()[0]
    assert saved["status"] == "failed"
    assert saved["input"] == {}


def test_unknown_tools_and_presentation_errors_do_not_fail_the_run():
    steps = ChatRunSteps(Mock(), Mock(side_effect=LookupError("missing tool")))
    steps.on_event(call("one", name="unknown_tool"))
    steps.on_event(result("one", facts={"not_json": object()}))
    step = steps.finish()[0]
    assert step["tool"] == step["presentation_type"] == "unknown_tool"
    assert step["status"] == "done"
    assert step["input"] == step["facts"] == {}
    assert not step["changes_data"]


def test_invalid_display_input_and_unmatched_results_are_ignored():
    steps = ChatRunSteps(Mock(), Mock(return_value={"input": {"count": float("nan")}}))
    steps.on_event(result("missing"))
    steps.on_event(call("one"))
    assert steps.finish()[0]["input"] == {}
