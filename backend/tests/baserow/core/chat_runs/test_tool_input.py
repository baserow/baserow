import json

import pytest

from baserow.core.chat_runs.tool_input import (
    MAX_INPUT_PREVIEW_SIZE,
    MAX_INPUT_PREVIEW_STRING_LENGTH,
    tool_input_preview,
)


def test_input_preview_copies_json_values_without_changing_the_arguments():
    values = {"fields": [{"name": "Plan", "primary": False, "count": 0, "x": None}]}

    preview = tool_input_preview(values)

    assert preview == {"values": values}
    preview["values"]["fields"][0]["name"] = "Changed only in display"
    assert values["fields"][0]["name"] == "Plan"


def test_input_preview_shortens_long_strings_and_keeps_every_other_value():
    values = {"id": 123456789012345, "fields": [{"name": "a" * 5000, "number": 7}]}

    preview = tool_input_preview(values)

    assert preview["truncated"] is True
    assert preview["values"]["id"] == 123456789012345
    assert preview["values"]["fields"][0]["number"] == 7
    name = preview["values"]["fields"][0]["name"]
    assert name == "a" * MAX_INPUT_PREVIEW_STRING_LENGTH + "…"


@pytest.mark.parametrize(
    "values",
    [
        {"ids": list(range(20_000))},
        {"fields": [{"name": "😀" * 1000} for _ in range(10)]},
        {"long key " * 3000: 1},
    ],
)
def test_input_preview_is_left_out_when_the_stored_json_is_too_large(values):
    assert len(json.dumps(values)) > MAX_INPUT_PREVIEW_SIZE
    assert tool_input_preview(values) == {}


def test_input_preview_size_is_counted_with_the_separators_used_when_stored():
    values = {"ids": [0] * 6000}

    assert len(json.dumps(values, separators=(",", ":"))) < MAX_INPUT_PREVIEW_SIZE
    assert tool_input_preview(values) == {}


@pytest.mark.parametrize("value", [object(), float("nan"), float("inf")])
def test_input_preview_is_left_out_for_values_that_are_not_json(value):
    assert tool_input_preview({"value": value}) == {}


def test_input_preview_is_left_out_for_circular_data():
    nested = {}
    nested["self"] = nested

    assert tool_input_preview(nested) == {}


def test_input_preview_removes_text_that_cannot_be_stored_in_jsonb():
    assert tool_input_preview({"name": "a\x00b\ud800c😀"}) == {
        "values": {"name": "abc😀"},
        "truncated": True,
    }
