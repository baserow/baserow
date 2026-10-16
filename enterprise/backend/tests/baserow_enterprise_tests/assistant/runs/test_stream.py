import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync

from baserow_enterprise.assistant.stream import stream_run_messages


def _collect(mocker, events, **kwargs):
    async def follow(*args, **options):
        for event in events:
            yield event

    follower = mocker.patch(
        "baserow_enterprise.assistant.stream.follow_run", side_effect=follow
    )

    async def collect():
        run = SimpleNamespace(id=uuid4(), chat_id=10, status="running")
        return [
            json.loads(record)
            async for record in stream_run_messages(run, object(), **kwargs)
        ]

    return async_to_sync(collect)(), follower


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


def test_baseline_rebuilds_without_repeating_live_effects_and_unavailable_preserves_text(
    mocker,
):
    records, _ = _collect(
        mocker,
        [
            {
                "kind": "run.baseline",
                "data": {"segment": 0, "text": "Known"},
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
    assert records[3]["content"] == "Known answer"
    assert records[4]["type"] == "chat-run-state"
    assert records[4]["_run"]["replay_unavailable"] is True


def test_terminal_saved_message_is_authoritative_and_has_one_cursor(mocker):
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
    assert len([r for r in records if r["_run"].get("cursor") == "last"]) == 1


@pytest.mark.parametrize(
    "human_message,replay",
    [(None, True), ({"type": "human", "content": "Hi", "id": 1}, False)],
)
def test_only_a_new_send_can_receive_navigation_before_first_read(
    mocker, human_message, replay
):
    _, follower = _collect(mocker, [], human_message=human_message)
    assert follower.call_args.kwargs["replay"] is replay


@pytest.mark.parametrize(
    "status,kind", [("cancelled", "ai/cancelled"), ("failed", "ai/error")]
)
def test_legacy_clients_keep_cancellation_and_error_variants_after_the_saved_result(
    mocker, status, kind
):
    records, _ = _collect(
        mocker,
        [
            {
                "kind": "run.finished",
                "data": {
                    "status": status,
                    "error_code": "interrupted",
                    "message": {"type": "ai/message", "id": 7, "content": "Partial"},
                },
                "cursor": "last",
            }
        ],
    )
    assert records[-2]["_run"]["status"] == status
    assert records[-2]["content"] == "Partial"
    assert records[-1]["type"] == kind
    assert "cursor" not in records[-1]["_run"]
    assert "status" not in records[-1]["_run"]
