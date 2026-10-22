import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync
from pytest_mock import MockerFixture

from baserow_enterprise.assistant.history import NOT_STARTED_ANSWER, UNFINISHED_ANSWER
from baserow_enterprise.assistant.stream import stream_run_messages


def _collect(
    mocker: MockerFixture, events: list[dict[str, Any]], **kwargs: Any
) -> tuple[list[dict[str, Any]], MagicMock]:
    async def follow(*args, **options):
        for event in events:
            yield event

    follower = mocker.patch(
        "baserow_enterprise.assistant.stream.follow_run", side_effect=follow
    )

    async def collect():
        run = SimpleNamespace(id=uuid4(), chat_id=10, status="running")
        return [record async for record in stream_run_messages(run, object(), **kwargs)]

    raw = async_to_sync(collect)()
    assert all(record.endswith("\n\n") for record in raw)
    return [json.loads(record) for record in raw], follower


def test_deltas_remain_cumulative_and_rewrites_replace_text(mocker):
    records, _ = _collect(
        mocker,
        [
            {
                "kind": "text.delta",
                "data": {"segment": 0, "text": "Hello"},
                "cursor": "c1",
            },
            {
                "kind": "text.delta",
                "data": {"segment": 0, "text": " world"},
                "cursor": "c2",
            },
            {
                "kind": "text.delta",
                "data": {"segment": 1, "text": "Revised"},
                "cursor": "c3",
            },
        ],
    )
    assert [
        record["content"] for record in records if record["type"] == "ai/message"
    ] == [
        "Hello",
        "Hello world",
        "Revised",
    ]
    assert [
        record["_run"]["cursor"] for record in records if record["_run"].get("cursor")
    ] == ["c1", "c2", "c3"]


def test_navigation_is_live_and_origin_only_but_every_cursor_advances(mocker):
    events = [
        {
            "kind": "navigation",
            "data": {"location": {"table_id": 5}, "origin_tab_id": tab},
            "cursor": f"c{index}",
            "replayed": replayed,
        }
        for index, (tab, replayed) in enumerate(
            [("origin", True), ("other", False), ("origin", False)]
        )
    ]
    records, _ = _collect(mocker, events, tab_id="origin")
    assert [
        record["_run"]["cursor"] for record in records if record["_run"].get("cursor")
    ] == ["c0", "c1", "c2"]
    assert [
        record["location"] for record in records if record["type"] == "ai/navigation"
    ] == [{"table_id": 5}]


def test_a_baseline_restarts_the_text_and_missing_replay_is_a_state_record(mocker):
    records, _ = _collect(
        mocker,
        [
            {
                "kind": "run.baseline",
                "data": {
                    "segment": 0,
                    "text": "Known",
                    "progress": {"text": "Creating rows"},
                },
                "cursor": "old",
                "replayed": True,
            },
            {
                "kind": "text.delta",
                "data": {"segment": 0, "text": " answer"},
                "cursor": "new",
            },
            {
                "kind": "run.replay_unavailable",
                "data": {"reason": "missing"},
                "replayed": True,
            },
        ],
    )
    assert records[2]["content"] == "Known"
    assert records[2]["_run"]["reset"] is True
    assert records[2]["_run"]["replay"] is True
    assert (records[3]["type"], records[3]["content"]) == (
        "ai/thinking",
        "Creating rows",
    )
    assert records[3]["_run"].keys() == {"id", "chat_id", "replay"}
    assert records[4]["content"] == "Known answer"
    assert records[5]["type"] == "chat-run-state"
    assert records[5]["_run"]["replay_unavailable"] is True


def test_terminal_saved_message_is_authoritative(mocker):
    message = {"type": "ai/message", "id": 7, "content": "Saved"}
    records, _ = _collect(
        mocker,
        [
            {
                "kind": "run.finished",
                "data": {"status": "completed", "message": message},
                "cursor": "last",
            }
        ],
    )
    assert records[-1] == {
        **message,
        "_run": {
            **records[-1]["_run"],
            "cursor": "last",
            "status": "completed",
            "error_code": "",
        },
    }


@pytest.mark.parametrize(
    "event,expected",
    [
        (
            {"kind": "progress", "data": {"text": "Searching..."}},
            {"type": "ai/thinking", "content": "Searching..."},
        ),
        (
            {"kind": "chat.title", "data": {"title": "A greeting"}},
            {"type": "chat/title", "content": "A greeting"},
        ),
    ],
)
def test_progress_and_title_map_to_kuma_records_after_a_cursorless_start(
    mocker, event, expected
):
    records, _ = _collect(mocker, [{**event, "cursor": "c1"}])

    started, record = records[1:]
    assert started["type"] == "ai/started"
    assert "cursor" not in started["_run"]
    assert record.items() >= expected.items()


HUMAN = {"type": "human", "content": "Hi", "id": 1}


@pytest.mark.parametrize(
    "human_message,replay", [(None, True), (HUMAN, False)], ids=["follow", "send"]
)
def test_the_message_shows_once_and_a_started_run_is_running(
    mocker, human_message, replay
):
    records, follower = _collect(
        mocker,
        [
            {"kind": "run.created", "data": {"human_message": HUMAN}, "cursor": "c0"},
            {"kind": "run.started", "data": {}, "cursor": "c1"},
        ],
        human_message=human_message,
    )

    assert [record["type"] for record in records].count("human") == 1
    assert records[-1]["type"] == "chat-run-state"
    assert (records[-1]["_run"]["cursor"], records[-1]["_run"]["status"]) == (
        "c1",
        "running",
    )
    assert follower.call_args.kwargs["replay"] is replay


@pytest.mark.parametrize(
    "status,error_code,expected",
    [
        ("cancelled", "interrupted", {"type": "ai/cancelled"}),
        (
            "failed",
            "interrupted",
            {"type": "ai/error", "code": "interrupted", "content": UNFINISHED_ANSWER},
        ),
        (
            "failed",
            "not_started",
            {"type": "ai/error", "code": "not_started", "content": NOT_STARTED_ANSWER},
        ),
        (
            "failed",
            "model_unavailable",
            {
                "type": "ai/error",
                "code": "model_unavailable",
                "content": NOT_STARTED_ANSWER,
            },
        ),
    ],
)
def test_legacy_clients_keep_cancellation_and_error_variants_after_the_saved_result(
    mocker, status, error_code, expected
):
    records, _ = _collect(
        mocker,
        [
            {
                "kind": "run.finished",
                "data": {
                    "status": status,
                    "error_code": error_code,
                    "message": {"type": "ai/message", "id": 7, "content": "Partial"},
                },
                "cursor": "last",
            }
        ],
    )
    assert records[-2]["_run"]["status"] == status
    assert records[-2]["content"] == "Partial"
    assert records[-1].items() >= expected.items()
    assert "cursor" not in records[-1]["_run"]
    assert "status" not in records[-1]["_run"]
