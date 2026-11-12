"""Translate the shared run stream into Kuma's existing JSON record protocol."""

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from django.contrib.auth.models import AbstractUser

from baserow.core.chat_runs.constants import ChatRunEventKind
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.chat_runs.stream import follow_run

from .history import NOT_STARTED_ANSWER, UNFINISHED_ANSWER
from .runs import CHAT_TITLE_EVENT, NAVIGATION_EVENT, NOTHING_RAN_ERROR_CODES
from .types import AiCancelledMessage, AiErrorMessage, AiStartedMessage


def _text_record(variant: str | None, text: str) -> dict[str, str]:
    return {"type": variant or "ai/message", "content": text}


async def stream_run_messages(
    run: ChatRun,
    user: AbstractUser,
    *,
    human_message: dict[str, Any],
    tab_id: str = "",
) -> AsyncIterator[str]:
    """
    Streams a run's output as Kuma's cumulative JSON records; disconnecting closes
    only this follower. Every Redis event yields at most one cursor-bearing
    record, including unknown events.

    :param run: The run to follow.
    :param user: The user following it.
    :param tab_id: The following tab, which receives navigation only if it sent
        the message.
    :param human_message: The message this send just saved: it is sent first,
        replacing the run.created echo. Reconnects use the core stream endpoint.
    :return: The JSON records, each followed by a blank line.
    """

    identity = {"id": str(run.id), "chat_id": run.chat_id}
    message_id = str(uuid4())
    yield (
        json.dumps({**human_message, "_run": {**identity, "status": run.status}})
        + "\n\n"
    )
    started = AiStartedMessage(message_id=message_id)
    yield json.dumps({**started.model_dump(), "_run": identity}) + "\n\n"
    text, segment = "", None
    async for event in follow_run(run, user, replay=False):
        kind, data = event.get("kind"), event.get("data") or {}
        if kind == "run.heartbeat":
            yield "\n\n"
            continue
        metadata = {**identity, "cursor": event.get("cursor")}
        replayed = event.get("replayed", False)
        if replayed:
            metadata["replay"] = True
        record = {"type": "chat-run-state"}
        if kind == ChatRunEventKind.TEXT_DELTA:
            if data.get("segment") != segment:
                text, segment = "", data.get("segment")
            text += data.get("text", "")
            record = _text_record(data.get("variant"), text)
        elif kind == "run.baseline":
            text, segment = data.get("text", ""), data.get("segment")
            metadata.update(reset=True, replay=True)
            record = _text_record(data.get("variant"), text)
        elif kind == "run.replay_unavailable":
            metadata["replay_unavailable"] = True
        elif kind == ChatRunEventKind.PROGRESS:
            record = {"type": "ai/thinking", "content": data.get("text", "")}
        elif kind == CHAT_TITLE_EVENT:
            record = {"type": "chat/title", "content": data.get("title", "")}
        elif kind == NAVIGATION_EVENT:
            if not replayed and data.get("origin_tab_id", "") == tab_id:
                record = {"type": "ai/navigation", "location": data["location"]}
        elif kind == ChatRunEventKind.RUN_CREATED:
            metadata["status"] = ChatRunStatus.QUEUED
        elif kind == ChatRunEventKind.RUN_STARTED:
            metadata["status"] = ChatRunStatus.RUNNING
        elif kind == ChatRunEventKind.RUN_FINISHED:
            metadata.update(
                status=data["status"], error_code=data.get("error_code", "")
            )
            record = data.get("message") or record
        yield json.dumps({**record, "_run": metadata}) + "\n\n"
        # Cursor-less: the follower drops a second record at the baseline's cursor.
        if kind == "run.baseline" and (progress := data.get("progress")):
            thinking = {"type": "ai/thinking", "content": progress["text"]}
            yield (
                json.dumps({**thinking, "_run": {**identity, "replay": True}}) + "\n\n"
            )
        # Tabs and API clients that predate runs end their answer on these.
        if kind == ChatRunEventKind.RUN_FINISHED:
            if data["status"] == ChatRunStatus.CANCELLED:
                cancelled = AiCancelledMessage(message_id=message_id)
                yield json.dumps({**cancelled.model_dump(), "_run": identity}) + "\n\n"
            elif data["status"] == ChatRunStatus.FAILED:
                error_code = data.get("error_code") or "unknown"
                nothing_ran = error_code in NOTHING_RAN_ERROR_CODES
                error = AiErrorMessage(
                    code=error_code,
                    content=NOT_STARTED_ANSWER if nothing_ran else UNFINISHED_ANSWER,
                )
                yield json.dumps({**error.model_dump(), "_run": identity}) + "\n\n"
