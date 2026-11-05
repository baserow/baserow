import json
import math
from typing import Any

MAX_INPUT_PREVIEW_SIZE = 16_384
MAX_INPUT_PREVIEW_NODES = 500
MAX_INPUT_PREVIEW_DEPTH = 8
MAX_INPUT_PREVIEW_STRING_LENGTH = 1000


def tool_input_preview(values: dict[str, Any]) -> dict[str, Any]:
    """Copy explicitly approved input values into a bounded display preview.

    This does not choose which arguments are safe to display. Each tool must
    select them first; credentials and other execution context must stay out.

    :param values: The tool's approved display values, never modified.
    :return: JSON-compatible values and a flag when any content was omitted.
    """

    remaining = MAX_INPUT_PREVIEW_SIZE
    nodes = MAX_INPUT_PREVIEW_NODES
    truncated = False

    def copy(value: Any, depth: int = 0) -> Any:
        nonlocal remaining, nodes, truncated
        nodes -= 1
        if isinstance(value, (dict, list)):
            remaining -= 2  # Reserve both brackets before visiting children.
            result = {} if isinstance(value, dict) else []
            items = value.items() if isinstance(value, dict) else enumerate(value)
            for key, child in items:
                if depth >= MAX_INPUT_PREVIEW_DEPTH or nodes <= 0 or remaining < 8:
                    truncated = True
                    break
                if isinstance(value, dict):
                    # Never shorten keys: that could rename a field or collide.
                    if (
                        not isinstance(key, str)
                        or "\x00" in key
                        or len(key) > MAX_INPUT_PREVIEW_STRING_LENGTH
                    ):
                        truncated = True
                        continue
                    try:
                        key.encode("utf-8")
                    except UnicodeEncodeError:
                        truncated = True
                        continue
                    cost = len(json.dumps(key)) + 2
                    if cost + 8 > remaining:
                        truncated = True
                        break
                    remaining -= cost
                    result[key] = copy(child, depth + 1)
                else:
                    remaining -= 1  # A comma, conservatively also for item one.
                    result.append(copy(child, depth + 1))
            return result

        if isinstance(value, str):
            clean = value.replace("\x00", "\ufffd")
            clean = clean.encode("utf-8", errors="replace").decode("utf-8")
            if clean != value:
                truncated = True
            limit = MAX_INPUT_PREVIEW_STRING_LENGTH
            if len(json.dumps(clean[:limit])) > remaining:
                # JSON escaping takes at most six characters per code unit.
                limit = max(0, (remaining - 8) // 12)
            if len(clean) > limit:
                clean = clean[:limit] + "…"
                truncated = True
            value = clean
        elif value is not None and (
            type(value) not in (bool, int, float)
            or (isinstance(value, float) and not math.isfinite(value))
        ):
            value = None
            truncated = True

        cost = len(json.dumps(value))
        if cost > remaining:
            value, cost = None, 4
            truncated = True
        remaining -= cost
        return value

    preview = {"values": copy(values)}
    if truncated:
        preview["truncated"] = True
    return preview
