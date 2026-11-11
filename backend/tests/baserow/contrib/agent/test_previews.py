import json

from pydantic import BaseModel

from baserow.contrib.agent.previews import (
    MASKED_VALUE,
    StepPreview,
    arguments_preview,
    as_requested,
    mask,
    name_field_references,
)
from baserow.core.chat_runs.tool_input import MAX_INPUT_PREVIEW_SIZE


class ViewRequest(BaseModel):
    name: str
    public: bool = False


def test_lists_and_keys_are_cut_at_any_depth_and_marked_cut():
    row = {"Tags": list(range(12)), **{f"F{index}": index for index in range(11)}}

    stored = StepPreview({"table": "Tasks"}, "rows", [row] * 15).to_input()

    kept = {"Tags": list(range(10)), **{f"F{index}": index for index in range(9)}}
    assert stored == {
        "values": {"table": "Tasks", "rows": [kept] * 10},
        "truncated": True,
    }


def test_short_requests_are_kept_whole():
    assert StepPreview({"table": "Tasks"}, "rows", [{"Name": "Acme"}]).to_input() == {
        "values": {"table": "Tasks", "rows": [{"Name": "Acme"}]}
    }
    assert StepPreview({"table": "Tasks"}).to_input() == {"values": {"table": "Tasks"}}


def test_a_request_too_large_to_store_keeps_its_names_and_the_items_that_fit():
    rows = [{"Notes": "x" * 1000, "Plan": "y" * 1000} for _ in range(10)]

    stored = StepPreview({"table": "Tasks"}, "rows", rows).to_input()

    assert stored["truncated"] is True
    assert stored["values"]["table"] == "Tasks"
    assert 0 < len(stored["values"]["rows"]) < 10
    assert stored["values"]["rows"] == rows[: len(stored["values"]["rows"])]
    assert len(json.dumps(stored["values"])) <= MAX_INPUT_PREVIEW_SIZE


def test_a_single_item_too_large_to_store_is_left_out_not_shown_empty():
    table = {f"F{index}": [{"x": "y" * 1000}] * 10 for index in range(10)}

    stored = StepPreview({"database": "Work"}, "tables", [table]).to_input()

    assert stored == {"values": {"database": "Work"}, "truncated": True}


def test_only_values_of_readable_fields_are_shown():
    values = {"Name": "Acme", "Secret": "a", "secret": "b", " Name": "c", "X": "d"}

    assert mask(values, {"Name"}) == {
        "Name": "Acme",
        "Secret": MASKED_VALUE,
        "secret": MASKED_VALUE,
        " Name": MASKED_VALUE,
        "X": MASKED_VALUE,
    }


def test_arguments_are_read_as_the_model_sent_them():
    assert as_requested({"table_id": 1, "views": [ViewRequest(name="Board")]}) == {
        "table_id": 1,
        "views": [{"name": "Board"}],
    }


def test_known_field_ids_become_names_and_unknown_ones_stay():
    named = name_field_references(
        {
            "column_field_id": 1,
            "field_options": [{"field_id": 2, "name": "Title"}],
            "date_field_id": 9,
        },
        {1: "Status", 2: "Name"},
    )

    assert named == {
        "column_field": "Status",
        "field_options": [{"field": "Name", "name": "Title"}],
        "date_field_id": 9,
    }


def test_arguments_preview_masks_credentials_at_any_depth():
    preview = arguments_preview(
        {
            "query": "open tickets",
            "api_key": "s3cret",
            "headers": {"Authorization": "Bearer s3cret", "Accept": "json"},
            "accounts": [{"name": "ops", "password": "hunter2"}],
            "max_tokens": 10,
        }
    )

    assert preview == {
        "values": {
            "query": "open tickets",
            "api_key": MASKED_VALUE,
            "headers": {"Authorization": MASKED_VALUE, "Accept": "json"},
            "accounts": [{"name": "ops", "password": MASKED_VALUE}],
            "max_tokens": MASKED_VALUE,
        }
    }


def test_arguments_preview_is_bounded_like_every_preview():
    preview = arguments_preview({"ids": list(range(50))})

    assert preview == {"values": {"ids": list(range(10))}, "truncated": True}
