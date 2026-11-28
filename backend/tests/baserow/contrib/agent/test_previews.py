import json

import pytest
from pydantic import BaseModel

from baserow.contrib.agent.previews import (
    MASKED_VALUE,
    StepPreview,
    arguments_preview,
    as_requested,
    held_previews,
    is_secret_name,
    mask,
    name_field_references,
)
from baserow.core.chat_runs.tool_input import (
    MAX_HELD_INPUT_SIZE,
    MAX_INPUT_PREVIEW_SIZE,
)


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
            "max_tokens": 10,
        }
    }


@pytest.mark.parametrize(
    "name",
    [
        "password",
        "Password",
        "pass",
        "passwd",
        "passphrase",
        "pass_phrase",
        "access_token",
        "accessToken",
        "accesstoken",
        "refresh-token",
        "X-Api-Key",
        "api_key",
        "apiKey",
        "APIKey",
        "apikey",
        "Authorization",
        "proxy_authorisation",
        "client_secret",
        "credentials",
        "private_key",
        "privateKey",
        "session_cookie",
        "passwords",
        "api_keys",
        "apiKeys",
        "access_tokens",
        "refresh_tokens",
        "private_keys",
    ],
)
def test_names_of_credentials_are_masked(name):
    assert is_secret_name(name)
    assert arguments_preview({name: "s3cret"}) == {"values": {name: MASKED_VALUE}}


@pytest.mark.parametrize(
    "name",
    [
        "passenger",
        "passengers",
        "passage",
        "bypass_cache",
        "compass",
        "tokenizer_mode",
        "max_tokens",
        "num_tokens",
        "keyword",
        "key",
        "author",
        "secretary",
    ],
)
def test_ordinary_names_that_contain_a_credential_word_are_shown(name):
    assert not is_secret_name(name)
    assert arguments_preview({name: "Ann"}) == {"values": {name: "Ann"}}


def test_a_held_call_shows_every_argument_whole():
    arguments = {
        "to": [f"person{index}@example.com" for index in range(25)],
        "body": "b" * 1910,
        "passenger": "Ann",
        "options": {f"option{index}": index for index in range(15)},
    }

    assert arguments_preview(arguments) == {"values": arguments}


def test_a_held_call_too_large_to_store_still_shows_its_arguments():
    arguments = {
        "subject": "Report",
        "body": "b" * 300_000,
        "to": ["ops@example.com"],
        "api_key": "s3cret",
    }

    preview = arguments_preview(arguments)

    assert len(json.dumps(preview["values"])) <= MAX_HELD_INPUT_SIZE
    assert preview["truncated"] is True
    assert preview["omitted_characters"] > 0
    assert "omitted_values" not in preview
    values = preview["values"]
    assert values["subject"] == "Report"
    assert values["to"] == ["ops@example.com"]
    assert values["api_key"] == MASKED_VALUE
    assert values["body"].startswith("b" * 100_000)
    assert len(values["body"]) == 300_000 - preview["omitted_characters"] + 1


def test_a_held_preview_names_and_shows_every_item():
    rows = [{f"F{index}": "x" * 1500 for index in range(11)} for _ in range(11)]

    with held_previews():
        preview = StepPreview({"table": "Tasks"}, "rows")
        preview.items = preview.cut_items(rows)

    assert preview.to_input() == {"values": {"table": "Tasks", "rows": rows}}
    assert StepPreview({"table": "Tasks"}, "rows", rows).to_input()["truncated"]


def test_a_held_preview_too_large_to_store_keeps_its_names_and_counts_the_rest():
    rows = [{"Name": f"Row {index}", "Notes": "y" * 50} for index in range(5000)]

    with held_previews():
        stored = StepPreview({"table": "Tasks"}, "rows", rows).to_input()

    assert len(json.dumps(stored["values"])) <= MAX_HELD_INPUT_SIZE
    assert stored["truncated"] is True
    assert stored["values"]["table"] == "Tasks"
    shown = stored["values"]["rows"]
    assert 1000 < len(shown) < len(rows)
    assert shown[:-1] == rows[: len(shown) - 1]
    assert shown[-1].items() <= rows[len(shown) - 1].items()
    assert stored["omitted_values"] == 2 * len(rows) - sum(map(len, shown))
    assert "omitted_characters" not in stored


def test_a_held_call_over_the_bounded_preview_size_is_not_shown_empty():
    arguments = {"sections": [{"paragraphs": ["x" * 190] * 10}] * 10}
    assert len(json.dumps(arguments)) > MAX_INPUT_PREVIEW_SIZE

    assert arguments_preview(arguments) == {"values": arguments}
