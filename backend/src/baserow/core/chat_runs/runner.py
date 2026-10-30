import asyncio
from contextlib import suppress

from django.db import transaction

from asgiref.sync import sync_to_async
from loguru import logger

from .buffer import close_buffer_redis
from .constants import (
    RUN_DEADLINE_SECONDS,
    ChatRunErrorCode,
    ChatRunEventKind,
    ChatRunStopReason,
)
from .handler import ChatRunHandler
from .journal import ChatRunJournal
from .models import ChatRun, ChatRunStatus
from .registries import ChatRunType
from .service import serialize_run
from .types import ChatRunOutcome


class _RunEndedElsewhere(Exception):
    """Roll back product writes if the conditional terminal transition loses."""


async def run_chat_run(run: ChatRun, run_type: ChatRunType) -> None:
    """Run inside ``execute_chat_run`` via ``async_to_sync``, outside HTTP.

    Await the adapter's ``execute`` while two local asyncio tasks flush output
    and renew the lease/check Stop. These are coroutines in this Celery task,
    not additional Celery jobs. Call synchronous ``_finish`` via ``sync_to_async``
    to save the outcome, then publish completion only after its commit.
    """

    journal = ChatRunJournal(run)
    journal.emit(ChatRunEventKind.RUN_STARTED, flush_now=True)
    background = [
        asyncio.create_task(journal.keep_flushing()),
        asyncio.create_task(journal.keep_alive()),
    ]
    deadline = asyncio.get_running_loop().call_later(
        RUN_DEADLINE_SECONDS, journal.request_stop, ChatRunStopReason.TIMEOUT
    )
    try:
        try:
            outcome = await run_type.execute(run, journal)
        except Exception as exc:
            logger.error("Chat run {} failed ({})", run.id, type(exc).__name__)
            outcome = ChatRunOutcome(ChatRunStatus.FAILED, ChatRunErrorCode.FAILED)
        if journal.stop_reason == ChatRunStopReason.LOST:
            return
        # The lease stays alive through final flush/persistence. Redis cannot
        # block control handling, and output failure cannot prevent final save.
        await journal.flush()
        snapshot = await sync_to_async(_finish)(run_type, run, outcome)
        if snapshot:
            await journal.publish_finished(snapshot)
    finally:
        deadline.cancel()
        for task in background:
            task.cancel()
        for task in background:
            with suppress(asyncio.CancelledError):
                await task
        await close_buffer_redis()


def _finish(
    run_type: ChatRunType, run: ChatRun, outcome: ChatRunOutcome
) -> dict | None:
    """Synchronous database section called by ``run_chat_run``'s sync bridge.

    Still part of the same Celery execution task. Lock the run, call the adapter's
    ``persist_outcome``, and call ``ChatRunHandler.finish_run`` in one transaction.
    """

    handler = ChatRunHandler()
    try:
        with transaction.atomic():
            if not handler.lock_running_run(run.id):
                return None
            message = run_type.persist_outcome(run, outcome)
            finished = handler.finish_run(
                run.id, outcome.status, outcome.error_code, message
            )
            if finished is None:
                raise _RunEndedElsewhere()
    except _RunEndedElsewhere:
        return None
    except Exception as exc:
        logger.error(
            "Could not save outcome of chat run {} ({})", run.id, type(exc).__name__
        )
    else:
        try:
            return serialize_run(finished)
        except Exception as exc:
            logger.error(
                "Could not serialize outcome of chat run {} ({})",
                run.id,
                type(exc).__name__,
            )
            return None

    # Product writes rolled back. Keep a durable started-run warning even if the
    # adapter cannot save its answer, so future history never claims no tools ran.
    with transaction.atomic():
        if not handler.lock_running_run(run.id):
            return None
        failed = handler.finish_run(
            run.id, ChatRunStatus.FAILED, ChatRunErrorCode.PERSIST_FAILED
        )
        try:
            with transaction.atomic():
                run_type.ensure_interruption_warning(failed)
        except Exception as exc:
            logger.error(
                "Could not preserve interruption warning for {} ({})",
                run.id,
                type(exc).__name__,
            )
    return serialize_run(failed)
