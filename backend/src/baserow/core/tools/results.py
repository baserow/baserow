"""Bound what a model reads of a tool's result, as it's resent in every later turn."""

import json
from typing import Any

from baserow.core.chat_runs.tool_input import shorten_text

CUT_MARK = "…"


def json_length(value: Any) -> int:
    """
    :param value: A JSON value.
    :return: How many characters a model reads of it as JSON.
    """

    return len(json.dumps(value, ensure_ascii=False))


def fit_values(values: dict[str, Any], max_length: int) -> dict[str, Any] | None:
    """
    Cut the values of an object so that it fits in about ``max_length``
    characters as JSON. In key order, a value stays whole when it fits in the
    space left, otherwise it's cut: a text to that space, ending with "…", any
    other value, like a list of files, to "…". Escaped characters of a cut text
    count once, so the result can be slightly longer.

    :param values: The object, never modified.
    :param max_length: The characters the object may take as JSON.
    :return: The object with its values cut, or None when even its keys don't fit.
    """

    empty_length = json_length("")
    left = max_length - json_length(dict.fromkeys(values, ""))
    if left < 0:
        return None
    fitted = {}
    for key, value in values.items():
        size = json_length(value) - empty_length
        if size > left:
            value = _cut(value, left)
            size = json_length(value) - empty_length
        fitted[key] = value
        left -= size
    return fitted


def _cut(value: Any, max_length: int) -> str:
    """
    :param value: A JSON value that doesn't fit.
    :param max_length: The characters left for it, without its quotes.
    :return: The start of a text ending with "…", "…" for any other value, or
        an empty text when there is no room for either.
    """

    if max_length <= 0:
        return ""
    if isinstance(value, str):
        return shorten_text(value, max_length)
    return CUT_MARK
