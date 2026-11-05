import json

import pytest

from baserow.core.chat_runs.tool_input import (
    MAX_INPUT_PREVIEW_NODES,
    MAX_INPUT_PREVIEW_SIZE,
    tool_input_preview,
)


def test_input_preview_copies_json_values_without_changing_the_arguments():
    values = {"rows": [{"Name": "Plan", "Done": False, "Count": 0, "Due": None}]}

    preview = tool_input_preview(values)

    assert preview == {"values": values}
    preview["values"]["rows"][0]["Name"] = "Changed only in display"
    assert values["rows"][0]["Name"] == "Plan"


@pytest.mark.parametrize(
    "value",
    [
        "a" * 20_000,
        "😀" * 20_000,
        '"\\\n' * 20_000,
        {"long key " * 3000: 1},
        list(range(20_000)),
        [{"Notes": "a" * 1000} for _ in range(100)],
    ],
)
def test_input_preview_bounds_serialized_size_and_marks_omissions(value):
    preview = tool_input_preview({"value": value})

    assert preview["truncated"] is True
    assert (
        len(json.dumps(preview["values"], separators=(",", ":")))
        <= MAX_INPUT_PREVIEW_SIZE
    )


def test_input_preview_stops_deep_and_circular_data():
    nested = {}
    nested["self"] = nested

    preview = tool_input_preview(nested)

    assert preview["truncated"] is True
    assert len(json.dumps(preview)) < 200


def test_input_preview_limits_scalar_nodes():
    preview = tool_input_preview({"ids": list(range(2000))})

    assert preview["truncated"] is True
    assert 0 < len(preview["values"]["ids"]) < MAX_INPUT_PREVIEW_NODES


@pytest.mark.parametrize("value", [object(), float("nan"), float("inf")])
def test_input_preview_omits_unsupported_values_without_stringifying_them(value):
    assert tool_input_preview({"value": value}) == {
        "values": {"value": None},
        "truncated": True,
    }


def test_input_preview_replaces_text_that_cannot_be_stored_in_jsonb():
    values = {
        "Name": "a\x00b\ud800",
        "bad\x00key": "value",
        "bad\ud800key": "value",
    }
    assert tool_input_preview(values) == {
        "values": {"Name": "a�b?"},
        "truncated": True,
    }
