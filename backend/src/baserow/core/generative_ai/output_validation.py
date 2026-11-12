"""Output checks shared by clients that let models call tools."""

import json
from collections.abc import Callable
from typing import Any

from pydantic_ai import ModelRetry, RunContext

ModelOutputValidator = Callable[[RunContext[Any], str], str]


_OPENER_CLOSERS = {"{": "}", "[": "]"}
_CLOSERS = frozenset(_OPENER_CLOSERS.values())


def parse_tool_call_envelope(value: Any) -> tuple[str, dict[str, Any]] | None:
    """
    Read a decoded JSON object containing exactly a tool name and arguments.

    :param value: The decoded value, without repairing or validating arguments.
    :return: The tool name and arguments, or None for another shape.
    """

    if (
        isinstance(value, dict)
        and value.keys() == {"name", "arguments"}
        and isinstance(value["name"], str)
        and isinstance(value["arguments"], dict)
    ):
        return value["name"], value["arguments"]
    return None


def _fix_closing_brackets(text: str) -> str:
    """
    Drop each ``"`` that sits between two closing brackets and, when the text
    ends with such a quote and a closing bracket, append the closing bracket
    that is missing if exactly one is.

    That ending, with one bracket missing, is how gpt-oss ends a call it prints
    (``}"}``). Any other missing bracket means the call was cut off, so it stays
    missing and the text does not parse. Only characters outside of strings
    count, so a string keeps its content.

    :param text: JSON text that does not parse.
    :return: The text with the repairs applied.
    """

    kept: list[str] = []
    missing: list[str] = []
    in_string = escaped = False
    last_dropped_quote_index: int | None = None
    for index, char in enumerate(text):
        if in_string:
            if char == '"' and not escaped:
                in_string = False
            escaped = char == "\\" and not escaped
        elif char == '"':
            if (
                text[index - 1 : index] in _CLOSERS
                and text[index + 1 : index + 2] in _CLOSERS
            ):
                last_dropped_quote_index = index
                continue
            in_string = True
        elif char in _OPENER_CLOSERS:
            missing.append(_OPENER_CLOSERS[char])
        elif char in _CLOSERS and missing:
            missing.pop()
        kept.append(char)
    ends_with_dropped_quote = last_dropped_quote_index == len(text.rstrip()) - 2
    closer = missing[0] if len(missing) == 1 and ends_with_dropped_quote else ""
    return "".join(kept) + closer


def repair_printed_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """
    Read a tool call that a model printed as JSON text, such as Groq's
    ``failed_generation``.

    Text that does not parse gets two repairs, and nothing else: a ``"`` between
    two closing brackets is dropped, and a text that ends with one (``}"}``) and
    misses exactly one closing bracket gets it appended.

    :param text: The printed tool call.
    :return: The tool name and its arguments, or None when the text is not an
        object with exactly a string ``name`` and an object ``arguments``.
    """

    try:
        call = json.loads(text)
    except (ValueError, RecursionError):
        try:
            call = json.loads(_fix_closing_brackets(text))
        except (ValueError, RecursionError):
            return None
    return parse_tool_call_envelope(call)


def get_printed_tool_call(
    ctx: RunContext[Any] | None, answer: str
) -> tuple[str, dict[str, Any]] | None:
    """
    Recognize a whole answer that is a JSON call to a currently offered tool.

    Kuma's narrow closing-bracket repairs also recognize malformed GPT-OSS calls.
    Prose, fenced examples, unrelated JSON, and unrepairable envelopes are left
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
    call = repair_printed_tool_call(answer)
    if call is None:
        return None
    tool_def = get_tool_def(call[0])
    if tool_def is None or tool_def.kind == "output":
        return None
    return call


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
