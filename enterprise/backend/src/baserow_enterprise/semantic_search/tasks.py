from django.conf import settings

from celery_singleton import Singleton

from baserow.config.celery import app

# The lock is taken when the task is queued, so it must also last while the task
# waits in the export queue, which can be busy for a long time. Otherwise a second
# task can index the same table at the same time.
LOCK_EXPIRY_SECONDS = 60 * 60


def _get_time_limit() -> int:
    # Leaves room to finish the current batch after the time budget is spent.
    return settings.BASEROW_SEMANTIC_SEARCH_TASK_TIME_BUDGET_SECONDS + 120


@app.task(
    queue="export",
    base=Singleton,
    unique_on="table_id",
    raise_on_duplicate=True,
    lock_expiry=max(LOCK_EXPIRY_SECONDS, _get_time_limit()),
    soft_time_limit=_get_time_limit(),
    time_limit=_get_time_limit() + 30,
)
def update_semantic_search_data(table_id: int):
    """
    :param table_id: The table of which the pending semantic search updates are
        processed.
    """

    from .handler import SemanticSearchHandler

    SemanticSearchHandler().get_search_data_updater_type().update(table_id)
