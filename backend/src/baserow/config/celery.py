import contextlib

from celery import Celery, signals

from baserow.config.helpers import check_lazy_loaded_libraries
from baserow.core.telemetry.tasks import BaserowTelemetryTask

app = Celery("baserow")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.Task = BaserowTelemetryTask


def clear_local(*args, **kwargs):
    """
    Clear the thread-local cache before and after each Celery task to prevent
    data leakage between tasks running on the same worker thread. It also clears the
    db_state, so that if there is a read-only replica, it will use that until a write
    query is executed.
    """

    from baserow.config.db_routers import clear_db_state
    from baserow.core.cache import local_cache

    local_cache.clear()
    clear_db_state()


def close_old_db_connections(sender, **kwargs):
    """
    Close old or unusable database connections around each Celery task.

    Calling `close_old_connections()` on both `task_prerun` and `task_postrun`
    ensures Django's own connection lifecycle is applied to Celery tasks, matching the
    documented recommendation for long-running processes.

    Eager tasks (used in tests) are skipped because they run inside the
    caller's process and share its database connection/transaction.
    """

    if getattr(sender.request, "is_eager", False):
        return

    from django.db import close_old_connections

    close_old_connections()


def _discard_connection_in_open_transaction(connection):
    """
    Drop a database connection that is still inside a transaction, so the next
    task gets a fresh one.

    Closing the connection while `in_atomic_block` is set would make Django keep
    the closed connection and flag it `closed_in_transaction`, after which every
    query fails with `InterfaceError: connection already closed` until the process
    exits. The atomic state is therefore reset first, so that `close()` releases
    the connection and the next query opens a new one. Closing it also makes
    PostgreSQL roll back the open transaction and release its locks.
    """

    connection.in_atomic_block = False
    connection.closed_in_transaction = False
    connection.needs_rollback = False
    connection.savepoint_ids = []
    connection.atomic_blocks = []
    connection.run_on_commit = []
    # `close()` releases the connection even if closing it fails, which is all
    # that is needed here.
    with contextlib.suppress(Exception):
        connection.close()


def recover_from_open_db_transaction(sender, **kwargs):
    """
    A task must never finish inside a database transaction: the connection would
    be unusable for every later task that runs in this worker process. If one
    does, the connection is discarded so the process stays healthy, and the
    occurrence is reported to Sentry and counted, because it is always a bug in
    the task.

    Connected before `close_old_db_connections` on `task_postrun`, so the connection
    is discarded before it can be flagged `closed_in_transaction`. It also recovers
    a connection that was already flagged.
    """

    if getattr(sender.request, "is_eager", False):
        return

    from django.db import connections

    open_aliases = [
        connection.alias
        for connection in connections.all(initialized_only=True)
        if connection.in_atomic_block
    ]
    if not open_aliases:
        return

    for alias in open_aliases:
        _discard_connection_in_open_transaction(connections[alias])

    import sentry_sdk
    from loguru import logger

    from baserow.core.telemetry.celery import (
        _get_task_queue,
        task_open_transaction_counter,
    )

    queue = _get_task_queue(sender)
    message = f"Celery task {sender.name} finished with an open database transaction"
    # A warning, because Sentry's Loguru integration would capture an error as a
    # second, ungrouped event. The error-level event is captured below.
    logger.warning(f"{message} on {', '.join(open_aliases)}.")
    with sentry_sdk.new_scope() as scope:
        scope.fingerprint = ["celery-task-open-database-transaction"]
        scope.set_tag("task_name", sender.name)
        scope.set_tag("queue", queue)
        scope.set_context(
            "open_database_transaction",
            {
                "task_id": kwargs.get("task_id"),
                "task_state": kwargs.get("state"),
                "database_aliases": open_aliases,
            },
        )
        sentry_sdk.capture_message(message, level="error")
    task_open_transaction_counter.add(1, {"task_name": sender.name, "queue": queue})


signals.task_prerun.connect(clear_local)
signals.task_prerun.connect(close_old_db_connections)
signals.task_postrun.connect(clear_local)
signals.task_postrun.connect(recover_from_open_db_transaction)
signals.task_postrun.connect(close_old_db_connections)


@signals.worker_process_init.connect
def on_worker_init(**kwargs):
    # Check that libraries meant to be lazy-loaded haven't been imported at startup.
    # This runs after Django is fully loaded, so it catches imports from all apps.
    check_lazy_loaded_libraries()
