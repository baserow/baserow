"""Output checks shared by clients that let models call tools."""

import json
from typing import Any

from pydantic_ai import ModelRetry, RunContext


def get_printed_tool_call(
    ctx: RunContext[Any] | None, answer: str
) -> tuple[str, dict[str, Any]] | None:
    """
    Recognize a whole answer that is a JSON call to a currently offered tool.

    Prose, fenced examples, unrelated JSON, and malformed envelopes are left
    alone. Recognizing a call never validates its arguments or executes it.

    :param ctx: The current run, or None outside one.
    :param answer: The candidate final answer.
    :return: The offered tool's name and arguments, or None.
    """

    if not isinstance(answer, str):
        return None
    tool_manager = getattr(ctx, "tool_manager", None)
    get_tool_def = getattr(tool_manager, "get_tool_def", None)
    if not callable(get_tool_def):
        return None
    try:
        call = json.loads(answer)
    except (ValueError, RecursionError):
        return None
    if (
        not isinstance(call, dict)
        or call.keys() != {"name", "arguments"}
        or not isinstance(call["name"], str)
        or not isinstance(call["arguments"], dict)
    ):
        return None
    tool_def = get_tool_def(call["name"])
    if tool_def is None or tool_def.kind == "output":
        return None
    return call["name"], call["arguments"]


def validate_tool_call_output(ctx: RunContext[Any], answer: str) -> str:
    """
    Ask the model to call an offered tool instead of printing its call as text.

    The retry stays in the existing run. The model must issue a real tool call,
    whose normal validation, permissions, and approvals still apply. The SDK's
    output retry limit bounds attempts; this check never repeats previous work.

    :param ctx: The current model run.
    :param answer: The candidate final answer.
    :return: The answer unchanged when it is not a printed tool call.
    :raises ModelRetry: When the whole answer names an offered tool as JSON.
    """

    if call := get_printed_tool_call(ctx, answer):
        raise ModelRetry(
            f"That answer prints a call to {call[0]} as text, so it did not run. "
            "Use the tool interface instead, then report its result. "
            "Do not repeat changes that already succeeded."
        )
    return answer
