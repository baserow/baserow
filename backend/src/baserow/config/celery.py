from django.conf import settings

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


signals.task_prerun.connect(clear_local)
signals.task_prerun.connect(close_old_db_connections)
signals.task_postrun.connect(clear_local)
signals.task_postrun.connect(close_old_db_connections)


@signals.worker_process_init.connect
def on_worker_init(**kwargs):
    # This is only needed in asgi.py
    settings.BASEROW_LAZY_LOADED_LIBRARIES.append("mcp")

    # Check that libraries meant to be lazy-loaded haven't been imported at startup.
    # This runs after Django is fully loaded, so it catches imports from all apps.
    check_lazy_loaded_libraries()
