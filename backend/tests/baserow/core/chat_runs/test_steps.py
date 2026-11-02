from unittest.mock import Mock

import pytest
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from baserow.core.chat_runs import steps as chat_steps
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
    "part,status,error_code",
    [
        (RetryPromptPart("Try again", tool_call_id="one"), "failed", "invalid_input"),
        (ToolReturnPart("tool", {"error": "denied"}, "one"), "failed", "failed"),
        (
            ToolReturnPart(
                "tool", {"deleted_field_ids": [], "errors": ["denied"]}, "one"
            ),
            "failed",
            "partial_failure",
        ),
        (
            ToolReturnPart(
                "tool",
                {"updated_fields": [{"id": 1}], "errors": ["other field denied"]},
                "one",
                metadata={"count": 1},
            ),
            "failed",
            "partial_failure",
        ),
        (ToolReturnPart("tool", None, "one", outcome="failed"), "failed", "failed"),
        (
            ToolReturnPart("tool", None, "one", outcome="denied"),
            "failed",
            "permission_denied",
        ),
        (
            ToolReturnPart("tool", None, "one", outcome="interrupted"),
            "stopped",
            None,
        ),
    ],
)
def test_failed_or_interrupted_calls_have_no_success_facts(part, status, error_code):
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one"))
    steps.on_event(FunctionToolResultEvent(part))
    assert steps.finish()[0]["status"] == status
    assert steps.finish()[0]["facts"] == {}
    if error_code is None:
        assert "error_code" not in steps.finish()[0]
    else:
        assert steps.finish()[0]["error_code"] == error_code


def test_invalid_call_is_failed_even_without_a_result_and_has_no_input():
    description = Mock(return_value={"input": {"requested_count": 99}})
    steps = ChatRunSteps(Mock(), description)
    steps.on_event(call("one", arguments={"rows": [1]}, valid=False))
    description.assert_called_once_with("create_rows", {})
    saved = steps.finish()[0]
    assert saved["status"] == "failed"
    assert saved["error_code"] == "invalid_input"
    assert saved["input"] == {}


def test_unknown_tools_and_presentation_errors_do_not_fail_the_run(logs, mocker):
    reported = mocker.spy(chat_steps, "report_exception")
    steps = ChatRunSteps(
        Mock(), Mock(side_effect=LookupError("PRIVATE_DESCRIPTION_ERROR_CANARY"))
    )
    steps.on_event(
        call(
            "one",
            name="PRIVATE_TOOL_CANARY",
            arguments={"search": "PRIVATE_ARGUMENT_CANARY"},
        )
    )
    steps.on_event(result("one", facts={"PRIVATE_FACTS_CANARY": object()}))
    step = steps.finish()[0]
    assert step["tool"] == step["presentation_type"] == "PRIVATE_TOOL_CANARY"
    assert step["status"] == "done"
    assert step["input"] == step["facts"] == {}
    assert not step["changes_data"]
    output = "".join(str(entry) for entry in logs)
    for private in (
        "PRIVATE_DESCRIPTION_ERROR_CANARY",
        "PRIVATE_TOOL_CANARY",
        "PRIVATE_ARGUMENT_CANARY",
        "PRIVATE_FACTS_CANARY",
    ):
        assert private not in output
    assert "LookupError" in output
    assert "TypeError" in output
    assert len(reported.call_args_list) == 2
    description_failure, display_failure = reported.call_args_list
    assert isinstance(description_failure.args[0], LookupError)
    assert description_failure.kwargs["context"] == {
        "tool": "PRIVATE_TOOL_CANARY",
        "phase": "step_description",
    }
    assert isinstance(display_failure.args[0], TypeError)
    assert display_failure.kwargs["context"] == {"phase": "step_display"}


def test_invalid_display_input_and_unmatched_results_are_ignored():
    steps = ChatRunSteps(Mock(), Mock(return_value={"input": {"count": float("nan")}}))
    steps.on_event(result("missing"))
    steps.on_event(call("one"))
    assert steps.finish()[0]["input"] == {}


@pytest.mark.parametrize(
    "code,expected",
    [
        ("not_found", "not_found"),
        ("permission_denied", "permission_denied"),
        ("invalid_input", "invalid_input"),
        ("partial_failure", "partial_failure"),
        ("failed", "failed"),
        ("PRIVATE_ERROR_MESSAGE", "failed"),
        ({"raw_error": "PRIVATE_ERROR_MESSAGE"}, "failed"),
        (None, "failed"),
    ],
)
def test_failed_steps_only_copy_allowlisted_error_codes(code, expected):
    journal = Mock()
    steps = ChatRunSteps(journal, describe)
    steps.on_event(call("one"))
    steps.on_event(
        result(
            "one",
            content={"error": "PRIVATE_ERROR_MESSAGE"},
            facts={"error_code": code, "traceback": "PRIVATE_TRACEBACK"},
        )
    )

    step = steps.finish()[0]
    assert step["error_code"] == expected
    assert step["facts"] == {}
    assert "PRIVATE" not in str(step)
    assert journal.emit.call_args.args[1] == step


@pytest.mark.parametrize(
    "outcome,status", [("success", "done"), ("interrupted", "stopped")]
)
def test_success_or_stop_clears_earlier_validation_error(outcome, status):
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one", valid=False))
    steps.on_event(result("one", outcome=outcome))

    step = steps.finish()[0]
    assert step["status"] == status
    assert "error_code" not in step
