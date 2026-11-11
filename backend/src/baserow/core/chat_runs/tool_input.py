import json
from typing import Any

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
    Copy display values into a bounded preview.

    :param values: The values to display, never modified.
    :return: The bounded copy, with long strings shortened and ``truncated`` when
        any was; or nothing when the stored JSON doesn't fit in
        ``MAX_INPUT_PREVIEW_SIZE`` characters. The caller decides what to drop.
    """

    try:
        dumped = json.dumps(_shorten_strings(values), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return {}
    if len(dumped) > MAX_INPUT_PREVIEW_SIZE:
        return {}
    preview = json.loads(dumped)
    if preview != values:
        return {"values": preview, "truncated": True}
    return {"values": preview}
