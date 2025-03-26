from celery import Celery, signals

from baserow.core.cache import local_cache

app = Celery("baserow")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


def clear_local_cache(*args, **kwargs):
    """
    Clear the thread-local cache before and after each Celery task to prevent
    data leakage between tasks running on the same worker thread.
    """

    local_cache.clear()


signals.task_prerun.connect(clear_local_cache)
signals.task_postrun.connect(clear_local_cache)
