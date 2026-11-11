from typing import Any

from django.db import DEFAULT_DB_ALIAS, transaction

from asgiref.sync import async_to_sync
from celery import Celery, Task
from loguru import logger

from baserow.config.celery import app
from baserow.config.db_routers import set_db_alias

from .constants import (
    CHAT_RUN_QUEUE,
    PRUNE_INTERVAL,
    RUN_TIME_LIMIT_SECONDS,
    SWEEP_INTERVAL,
    WAITING_WARNING_AFTER,
    ChatRunErrorCode,
)
from .handler import ChatRunHandler
from .models import ChatRunStatus
from .registries import chat_run_type_registry
from .runner import run_chat_run


@app.task(
    bind=True,
    queue=CHAT_RUN_QUEUE,
    ignore_result=True,
    acks_late=False,
    max_retries=0,
    soft_time_limit=RUN_TIME_LIMIT_SECONDS,
    time_limit=RUN_TIME_LIMIT_SECONDS,
)
def execute_chat_run(self: Task, run_id: str) -> None:
    """
    Celery worker entry point, enqueued by ``ChatRunHandler.start_run`` on commit.

    Claim the run synchronously, then use ``async_to_sync`` to run the async
    ``run_chat_run`` runner. This happens independently of the HTTP follower.
    It is never retried, because a retry would repeat the changes its tools
    already made. The soft limit equals the hard limit, so the global soft limit
    never interrupts the run's own deadline.

    :param run_id: The id of the queued run.
    """

    set_db_alias(DEFAULT_DB_ALIAS)
    handler = ChatRunHandler()
    run = handler.claim_run(run_id)
    if run is None:
        return

    try:
        run_type = chat_run_type_registry.get(run.run_type)
    except chat_run_type_registry.does_not_exist_exception_class:
        logger.error("The chat run {} has the unknown type {}", run.id, run.run_type)
        with transaction.atomic():
            ended = handler.finish_run(
                run.id, ChatRunStatus.FAILED, ChatRunErrorCode.FAILED
            )
            if ended is not None:
                transaction.on_commit(
                    lambda: handler._publish_terminal(ended), robust=True
                )
        return

    async_to_sync(run_chat_run)(run, run_type)


@app.task(bind=True, ignore_result=True)
def sweep_chat_runs(self: Task) -> None:
    """
    Periodic Celery task calling the handler's synchronous recovery methods.

    End runs whose worker died and runs no worker picked up in time. This task
    does not rerun adapters' ``execute`` methods.
    """

    handler = ChatRunHandler()
    handler.finalize_lost_runs()
    handler.fail_not_started_runs()
    waiting = handler.count_runs_newly_waiting_too_long()
    if waiting:
        logger.warning(
            "{} chat runs have waited more than {} minutes for a worker; check "
            "that a worker consumes the chat_run queue",
            waiting,
            int(WAITING_WARNING_AFTER.total_seconds() // 60),
        )


@app.task(bind=True, ignore_result=True)
def prune_chat_runs(self: Task) -> None:
    """
    Periodic Celery task deleting one page through ``ChatRunHandler.prune``.

    Enqueue itself again while pages are full. Adapter warning hooks run
    synchronously in this task before deletion.
    """

    if ChatRunHandler().prune():
        prune_chat_runs.delay()


@app.on_after_finalize.connect
def setup_periodic_chat_run_tasks(sender: Celery, **kwargs: Any) -> None:
    """
    Schedules the sweeper and the pruning.

    :param sender: The Celery app.
    """

    sender.add_periodic_task(SWEEP_INTERVAL, sweep_chat_runs.s())
    sender.add_periodic_task(PRUNE_INTERVAL, prune_chat_runs.s())
