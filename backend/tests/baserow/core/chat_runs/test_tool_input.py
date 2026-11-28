import json

import pytest

from baserow.core.chat_runs.tool_input import (
    MAX_HELD_INPUT_SIZE,
    MAX_INPUT_PREVIEW_SIZE,
    MAX_INPUT_PREVIEW_STRING_LENGTH,
    MIN_HELD_INPUT_STRING_LENGTH,
    held_tool_input,
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
    assert name == "a" * (MAX_INPUT_PREVIEW_STRING_LENGTH - 1) + "…"


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


def test_held_input_keeps_every_value_whole_up_to_its_size():
    values = {"ids": list(range(10_000)), "body": "a" * 100_000}

    assert held_tool_input(values) == {"values": values}


@pytest.mark.parametrize(
    "values",
    [
        {"ids": list(range(100_000))},
        {"body": "😀" * 100_000, "to": ["ops@example.com"]},
        {"notes": ["x" * 1000] * 1000, "table": "Tasks"},
        {"rows": [{f"F{index}": "y" * 10 for index in range(50_000)}]},
    ],
)
def test_held_input_too_large_to_store_shows_what_fits_and_counts_the_rest(values):
    held = held_tool_input(values)

    assert len(json.dumps(held["values"])) <= MAX_HELD_INPUT_SIZE
    assert held["truncated"] is True
    assert held.get("omitted_values", 0) + held.get("omitted_characters", 0) > 0
    assert set(held["values"]) == set(values)
    for key, value in held["values"].items():
        assert value, key


def test_held_input_cuts_long_texts_before_leaving_values_out():
    values = {"notes": ["x" * 1000] * 1000, "table": "Tasks"}

    held = held_tool_input(values)

    assert "omitted_values" not in held
    assert len(held["values"]["notes"]) == 1000
    length = len(held["values"]["notes"][0])
    assert MIN_HELD_INPUT_STRING_LENGTH < length < 1000
    assert held["omitted_characters"] == 1000 * (1000 - length + 1)
    assert held["values"]["table"] == "Tasks"


@pytest.mark.parametrize("value", [object(), float("nan")])
def test_held_input_is_left_out_for_values_that_are_not_json(value):
    assert held_tool_input({"value": value}) == {}
