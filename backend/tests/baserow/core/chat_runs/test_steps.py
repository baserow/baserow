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


def test_a_partly_completed_batch_is_done_with_the_count_the_tool_reports():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one"))
    steps.on_event(
        result(
            "one",
            content={"updated_fields": [{"id": 1}], "errors": ["Field 2 denied"]},
            facts={"count": 1},
        )
    )

    step = steps.finish()[0]
    assert (step["status"], step["facts"]) == ("done", {"count": 1})
    assert "error_code" not in step


def test_invalid_call_is_failed_even_without_a_result_and_has_no_input():
    description = Mock(return_value={"input": {"requested_count": 99}})
    steps = ChatRunSteps(Mock(), description)
    steps.on_event(call("one", arguments={"rows": [1]}, valid=False))
    description.assert_called_once_with("create_rows", {})
    saved = steps.finish()[0]
    assert saved["status"] == "failed"
    assert saved["error_code"] == "invalid_input"
    assert saved["input"] == {}


def retry(call_id):
    return FunctionToolResultEvent(RetryPromptPart("Fix it", tool_call_id=call_id))


def test_a_retry_continues_the_step_of_its_invalid_attempt_but_not_of_siblings():
    journal = Mock()
    steps = ChatRunSteps(journal, describe)
    steps.on_event(call("invalid", valid=False))
    steps.on_event(call("sibling", arguments={"rows": [1]}))
    steps.on_event(retry("invalid"))
    steps.on_event(result("sibling", facts={"count": 1}))
    steps.on_event(call("retry", arguments={"rows": [1, 2]}))
    steps.on_event(result("retry", facts={"count": 2}))

    saved = steps.finish()
    first = journal.emit.call_args_list[0].args[1]
    assert [(step["status"], step["facts"]) for step in saved] == [
        ("done", {"count": 1}),
        ("done", {"count": 2}),
    ]
    assert saved[1]["id"] == first["id"]
    assert "error_code" not in saved[1]


def test_only_the_next_response_can_retry_an_invalid_call():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("invalid", valid=False))
    steps.on_event(retry("invalid"))
    steps.on_event(call("read", name="list_tables"))
    steps.on_event(result("read"))
    steps.on_event(call("later", arguments={"rows": [1]}))

    assert [step["status"] for step in steps.finish()] == [
        "failed",
        "done",
        "stopped",
    ]


def test_a_call_that_runs_out_of_retries_leaves_one_failed_step():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one", valid=False))
    steps.on_event(retry("one"))
    steps.on_event(call("two", valid=False))

    saved = steps.finish()
    assert [(step["status"], step["error_code"]) for step in saved] == [
        ("failed", "invalid_input")
    ]


def test_unknown_tools_and_presentation_errors_do_not_fail_the_run(logs):
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
    assert step["tool"] == "PRIVATE_TOOL_CANARY"
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


def test_an_error_object_fails_the_step_with_its_message_and_items():
    journal = Mock()
    steps = ChatRunSteps(journal, describe)
    steps.on_event(call("one", arguments={"rows": [{}]}))
    steps.on_event(
        result(
            "one",
            content={
                "changed": False,
                "error": {"code": "conflict", "message": "A exists."},
                "errors": [
                    {
                        "item": "A",
                        "code": "conflict",
                        "message": "A exists.",
                        "hint": "x",
                    }
                ],
            },
        )
    )

    (step,) = steps.finish()
    assert (step["status"], step["error_code"], step["error_message"]) == (
        "failed",
        "conflict",
        "A exists.",
    )
    assert step["item_errors"] == [
        {"item": "A", "code": "conflict", "message": "A exists."}
    ]


def test_a_call_that_changed_nothing_without_errors_is_skipped():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one", arguments={"rows": [{}]}))
    steps.on_event(result("one", content={"changed": False}, facts={"count": 0}))

    assert [step["status"] for step in steps.finish()] == ["skipped"]


def test_a_partial_batch_is_done_with_its_displayable_failed_items():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one", arguments={"rows": [{}, {}]}))
    unusable = [{"item": "x", "code": "failed"}, {"item": "y", "message": " "}]
    errors = unusable + [
        {"item": i, "code": "invalid_input", "message": "Bad."} for i in range(25)
    ]
    steps.on_event(
        result("one", content={"changed": True, "errors": errors}, facts={"count": 1})
    )

    (step,) = steps.finish()
    assert step["status"] == "done" and len(step["item_errors"]) == 20
    assert step["item_errors"][0]["item"] == 0


def test_a_retry_after_a_failed_result_continues_the_failed_step():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one", arguments={"rows": [{}]}))
    steps.on_event(
        result("one", content={"error": {"code": "failed", "message": "No."}})
    )
    steps.on_event(call("two", arguments={"rows": [{}]}))
    steps.on_event(result("two", content={"changed": True}, facts={"count": 1}))

    (step,) = steps.finish()
    assert step["status"] == "done" and "error_message" not in step


@pytest.mark.parametrize("error", ["Not allowed.", ["Not allowed."]])
def test_errors_that_are_not_objects_fail_the_step_without_a_message(error):
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one"))
    steps.on_event(result("one", content={"error": error}))

    (step,) = steps.finish()
    assert step["status"] == "failed" and "error_message" not in step


def test_a_retry_that_changes_nothing_keeps_the_earlier_failure():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one", arguments={"rows": [{}]}))
    failure = {"error": {"code": "conflict", "message": "A exists."}}
    steps.on_event(result("one", content=failure))
    steps.on_event(call("two", arguments={"rows": [{}]}))
    steps.on_event(result("two", content={"changed": False}))

    (step,) = steps.finish()
    assert (step["status"], step["error_code"], step["error_message"]) == (
        "failed",
        "conflict",
        "A exists.",
    )


def test_a_denied_call_is_not_continued_by_the_next_call():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one", arguments={"rows": [{}]}))
    steps.on_event(result("one", outcome="denied"))
    steps.on_event(call("two", arguments={"rows": [{}]}))
    steps.on_event(result("two", facts={"count": 1}))

    assert [step["status"] for step in steps.finish()] == ["failed", "done"]


def test_messages_for_people_are_shortened_and_hints_left_out():
    steps = ChatRunSteps(Mock(), describe)
    steps.on_event(call("one", arguments={"rows": [{}]}))
    long_message = "x" * 1500
    error = {"code": "invalid_input", "message": long_message, "hint": "HINT_CANARY"}
    steps.on_event(
        result(
            "one",
            content={
                "changed": False,
                "error": error,
                "errors": [{"item": 0, **error}],
            },
        )
    )

    (step,) = steps.finish()
    assert step["error_message"] == "x" * 999 + "…"
    assert step["item_errors"][0]["message"] == "x" * 999 + "…"
    assert "HINT_CANARY" not in str(step)
