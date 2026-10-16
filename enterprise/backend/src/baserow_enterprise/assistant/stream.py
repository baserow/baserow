"""Translate the shared run stream into Kuma's existing JSON record protocol."""

import json
from collections.abc import AsyncIterator
from uuid import uuid4

from baserow.core.chat_runs.constants import (
    PROGRESS,
    RUN_CANCEL_REQUESTED,
    RUN_CREATED,
    RUN_FINISHED,
    RUN_STARTED,
    TEXT_DELTA,
)
from baserow.core.chat_runs.models import ChatRun
from baserow.core.chat_runs.stream import follow_run

from .runs import CHAT_TITLE_EVENT, NAVIGATION_EVENT


async def stream_run_messages(
    run: ChatRun,
    user,
    *,
    cursor: str | None = None,
    tab_id: str = "",
    human_message: dict | None = None,
) -> AsyncIterator[str]:
    """Follow existing work; disconnecting closes only this output follower.

    The adapter folds shared deltas back into cumulative Kuma chunks. Every Redis
    event yields at most one cursor-bearing record, including unknown events.
    """

    identity = {"id": str(run.id), "chat_id": run.chat_id}
    message_id = str(uuid4())
    initial = human_message or {"type": "chat-run-state"}
    yield json.dumps({**initial, "_run": {**identity, "status": run.status}}) + "\n\n"
    yield (
        json.dumps({"type": "ai/started", "message_id": message_id, "_run": identity})
        + "\n\n"
    )
    text, segment = "", None
    async for event in follow_run(
        run, user, cursor=cursor, replay=human_message is None
    ):
        kind, data = event.get("kind"), event.get("data") or {}
        if kind == "run.heartbeat":
            yield "\n\n"
            continue
        metadata = {**identity, "cursor": event.get("cursor")}
        replayed = event.get("replayed", False)
        if replayed:
            metadata["replay"] = True
        record = {"type": "chat-run-state"}
        if kind == TEXT_DELTA:
            if data.get("segment") != segment:
                text, segment = "", data.get("segment")
            text += data.get("text", "")
            variant = data.get("variant", "ai/message")
            record = {
                "type": variant
                if variant in ("ai/message", "ai/reasoning")
                else "ai/message",
                "content": text,
            }
        elif kind == "run.baseline":
            text, segment = data.get("text", ""), data.get("segment")
            metadata.update(reset=True, replay=True)
            variant = data.get("variant", "ai/message")
            record = {
                "type": variant
                if variant in ("ai/message", "ai/reasoning")
                else "ai/message",
                "content": text,
            }
        elif kind == "run.replay_unavailable":
            metadata["replay_unavailable"] = True
        elif kind == PROGRESS:
            record = {"type": "ai/thinking", "content": data.get("text", "")}
        elif kind == CHAT_TITLE_EVENT:
            record = {"type": "chat/title", "content": data.get("title", "")}
        elif kind == NAVIGATION_EVENT:
            if not replayed and data.get("origin_tab_id", "") == tab_id:
                record = {
                    "type": "ai/navigation",
                    "location": data["location"],
                    "origin_tab_id": data.get("origin_tab_id", ""),
                }
        elif kind == RUN_CREATED:
            metadata["status"] = "queued"
            if human_message is None and data.get("human_message"):
                record = data["human_message"]
        elif kind == RUN_STARTED:
            metadata["status"] = "running"
        elif kind == RUN_CANCEL_REQUESTED:
            metadata["cancel_requested"] = True
        elif kind == RUN_FINISHED:
            metadata.update(
                status=data["status"], error_code=data.get("error_code", "")
            )
            record = data.get("message") or record
        yield json.dumps({**record, "_run": metadata}) + "\n\n"
        # Existing JSON-record clients use these variants to display Stop/errors.
        # The shared follower has already accepted the authoritative terminal
        # message and ignores this cursor-less compatibility record.
        if kind == RUN_FINISHED and data["status"] == "cancelled":
            yield (
                json.dumps(
                    {"type": "ai/cancelled", "message_id": message_id, "_run": identity}
                )
                + "\n\n"
            )
        elif kind == RUN_FINISHED and data["status"] == "failed":
            yield (
                json.dumps(
                    {
                        "type": "ai/error",
                        "code": data.get("error_code") or "unknown",
                        "content": "I couldn't finish this response. Some changes may already have been made.",
                        "_run": identity,
                    }
                )
                + "\n\n"
            )
