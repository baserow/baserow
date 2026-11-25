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


def fit_result(result: Any, max_length: int) -> Any:
    """
    Cut a tool's result so that it fits in about ``max_length`` characters as
    JSON. The items of a list under ``results`` are kept whole from the start
    while they fit, as the first ones matter most, and the others are left out.
    When not even the first one fits, its values are cut. Any other object has
    its values cut, and any other value is cut as text.

    :param result: The result as a JSON value, never modified.
    :param max_length: The characters the result may take as JSON.
    :return: The result, with ``truncated`` set on an object that was cut.
    """

    if json_length(result) <= max_length:
        return result
    if not isinstance(result, dict):
        text = result if isinstance(result, str) else json.dumps(result)
        return shorten_text(text, max_length)
    if not isinstance(result.get("results"), list):
        max_length -= json_length({"truncated": True})
        return {**(fit_values(result, max_length) or {}), "truncated": True}
    fitted = {**result, "results": [], "truncated": True}
    left = max_length - json_length(fitted)
    for item in result["results"]:
        # The separator between two items counts too.
        size = json_length(item) + 2
        if size > left:
            if not fitted["results"] and isinstance(item, dict):
                cut_item = fit_values(item, left)
                if cut_item is not None:
                    fitted["results"].append(cut_item)
            break
        fitted["results"].append(item)
        left -= size
    return fitted
