from celery import Celery, signals

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


signals.task_prerun.connect(clear_local)
signals.task_postrun.connect(clear_local)
