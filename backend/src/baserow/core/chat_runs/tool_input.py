import json
from typing import Any

from baserow.core.utils import remove_invalid_surrogate_characters

MAX_INPUT_PREVIEW_SIZE = 16_384
MAX_INPUT_PREVIEW_STRING_LENGTH = 1000


def shorten_text(value: str, max_length: int) -> str:
    """
    Cut text that is too long, marking the cut with an ellipsis.

    :param value: The text to bound.
    :param max_length: The most characters the result may have.
    :return: The text, or its start and "…" within ``max_length`` characters.
    """

    if len(value) > max_length:
        return value[: max_length - 1] + "…"
    return value


def _shorten_strings(value: Any) -> Any:
    if isinstance(value, str):
        return shorten_text(value, MAX_INPUT_PREVIEW_STRING_LENGTH)
    if isinstance(value, dict):
        return {key: _shorten_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_shorten_strings(item) for item in value]
    return value


def tool_input_preview(values: dict[str, Any]) -> dict[str, Any]:
    """
    Copy explicitly approved input values into a bounded display preview.

    This does not choose which arguments are safe to display. Each tool must
    select them first; credentials and other execution context must stay out.

    :param values: The tool's approved display values, never modified.
    :return: The values with long strings shortened and text PostgreSQL can't
        store removed, and ``truncated`` when anything changed. Nothing when the
        stored JSON would exceed ``MAX_INPUT_PREVIEW_SIZE`` characters, because a
        partial copy could misstate the request.
    """

    try:
        dumped = json.dumps(_shorten_strings(values), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return {}
    stored = remove_invalid_surrogate_characters(dumped.encode("utf-8"), "utf-8")
    if len(stored) > MAX_INPUT_PREVIEW_SIZE:
        return {}
    preview = json.loads(stored)
    if preview != values:
        return {"values": preview, "truncated": True}
    return {"values": preview}
