import json
from typing import Any

MAX_INPUT_PREVIEW_SIZE = 16_384
MAX_INPUT_PREVIEW_STRING_LENGTH = 1000
# A held call's input is shown whole up to this many characters of JSON.
MAX_HELD_INPUT_SIZE = 256 * 1024
# Over it, no text is cut shorter than this, so values are left out instead.
MIN_HELD_INPUT_STRING_LENGTH = 100


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


def _shorten_strings(
    value: Any, max_length: int = MAX_INPUT_PREVIEW_STRING_LENGTH
) -> Any:
    if isinstance(value, str):
        return shorten_text(value, max_length)
    if isinstance(value, dict):
        return {key: _shorten_strings(item, max_length) for key, item in value.items()}
    if isinstance(value, list):
        return [_shorten_strings(item, max_length) for item in value]
    return value


def _size(value: Any) -> int:
    return len(json.dumps(value, allow_nan=False))


def _cut_characters(value: Any, max_length: int) -> int:
    """
    :return: How many characters ``_shorten_strings(value, max_length)`` cuts.
    """

    if isinstance(value, str):
        return len(value) - (max_length - 1) if len(value) > max_length else 0
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return sum(_cut_characters(item, max_length) for item in value)
    return 0


def _count_values(value: Any) -> int:
    """
    :return: How many values a left out value holds: its items and entries, at
        any depth, or 1 for a single value.
    """

    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return sum(_count_values(item) for item in value) or 1
    return 1


class _Room:
    """What still fits of a held call's input, and what was left out."""

    def __init__(self, size: int) -> None:
        self.left = size
        self.omitted_values = 0
        self.full = False

    def fit(self, value: dict | list) -> dict | list:
        """
        :param value: An object or list too large for the room left, whose
            brackets are already counted.
        :return: Its entries or items in reading order until one doesn't fit:
            of that one only the start that fits, of the following ones nothing.
        """

        is_dict = isinstance(value, dict)
        fitted = {} if is_dict else []
        for key, item in value.items() if is_dict else enumerate(value):
            # Separators are counted for every entry, the first one too.
            cost = _size(str(key)) + 4 if is_dict else 2
            if not self.full and self._take(cost + _size(item)):
                part = item
            elif (
                not self.full
                and isinstance(item, (dict, list))
                and self._take(cost + 2)
            ):
                part = self.fit(item)
                if not part:
                    # Nothing of it fit, which counted its values: it's left out.
                    self.left += cost + 2
                    continue
            else:
                # Everything after the first value that doesn't fit is left out.
                self.full = True
                self.omitted_values += _count_values(item)
                continue
            if is_dict:
                fitted[key] = part
            else:
                fitted.append(part)
        return fitted

    def _take(self, size: int) -> bool:
        if size > self.left:
            return False
        self.left -= size
        return True


def held_tool_input(values: dict[str, Any]) -> dict[str, Any]:
    """
    Copy what the person deciding on a held call reads: every value whole, as the
    call sends it, while the JSON fits in ``MAX_HELD_INPUT_SIZE`` characters.
    Larger, the longest texts are cut first, down to
    ``MIN_HELD_INPUT_STRING_LENGTH`` characters, and then trailing items and
    entries are left out until it fits: the input is never left empty.

    :param values: The values to display, never modified.
    :return: ``values``, and when anything was left out ``truncated``, with
        ``omitted_characters`` cut from texts and ``omitted_values``, the number of
        values left out. Nothing only for values that aren't JSON.
    """

    try:
        if _size(values) <= MAX_HELD_INPUT_SIZE:
            return {"values": json.loads(json.dumps(values))}
        low, high = MIN_HELD_INPUT_STRING_LENGTH, MAX_HELD_INPUT_SIZE
        while low < high:
            middle = (low + high + 1) // 2
            if _size(_shorten_strings(values, middle)) <= MAX_HELD_INPUT_SIZE:
                low = middle
            else:
                high = middle - 1
        shortened = _shorten_strings(values, low)
        room = _Room(MAX_HELD_INPUT_SIZE - 2)
        if _size(shortened) > MAX_HELD_INPUT_SIZE:
            shortened = room.fit(shortened)
    except (TypeError, ValueError, RecursionError):
        return {}
    held: dict[str, Any] = {"values": shortened, "truncated": True}
    if omitted_characters := _cut_characters(values, low):
        held["omitted_characters"] = omitted_characters
    if room.omitted_values:
        held["omitted_values"] = room.omitted_values
    return held


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
