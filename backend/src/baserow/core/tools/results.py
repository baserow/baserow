"""Bound what a model reads of a tool's result, as it's resent in every later turn."""

import json
from typing import Any

from baserow.core.chat_runs.tool_input import shorten_text


def json_length(value: Any) -> int:
    """
    :param value: A JSON value.
    :return: How many characters a model reads of it as JSON.
    """

    return len(json.dumps(value, ensure_ascii=False))


def fit_text_values(values: dict[str, Any], max_length: int) -> dict[str, Any] | None:
    """
    Cut the text values of an object, in key order, so that it fits in about
    ``max_length`` characters as JSON. The first values stay whole as long as
    they fit, the one that doesn't is cut and ends with "…", and the values after
    it become empty. Escaped characters, like a new line, count once, so the
    result can be slightly longer.

    :param values: The object, never modified.
    :param max_length: The characters the object may take as JSON.
    :return: The object with its text values cut, or None when even its other
        values don't fit.
    """

    text_keys = [key for key, value in values.items() if isinstance(value, str)]
    left = max_length - json_length({**values, **{key: "" for key in text_keys}})
    if left < 0:
        return None
    fitted = dict(values)
    for key in text_keys:
        text = values[key]
        if len(text) > left:
            # `shorten_text` needs room for its "…".
            text = shorten_text(text, left) if left > 0 else ""
        fitted[key] = text
        left -= len(text)
    return fitted
