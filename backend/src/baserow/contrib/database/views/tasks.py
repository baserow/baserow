import traceback
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, transaction

from celery_singleton import DuplicateTaskError, Singleton
from loguru import logger

from baserow.config.celery import app
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.database.views.handler import (
    ViewIndexingHandler,
    ViewSubscriptionHandler,
)

AUTO_INDEX_CACHE_KEY = "auto_index_view_cache_key"


def get_auto_index_cache_key(view_id):
    return f"{AUTO_INDEX_CACHE_KEY}:{view_id}"


@app.task(
    base=Singleton,
    queue="export",
    lock_expiry=settings.AUTO_INDEX_LOCK_EXPIRY,
    raise_on_duplicate=True,
)
def update_view_index(view_id: int):
    """
    Create/update the index for the provided view if needed.

    :param view_id: The id of the view for which the index should be updated.
    """

    recheck_delay = 0
    try:
        ViewIndexingHandler.update_index_by_view_id(view_id)

    except ViewDoesNotExist:
        return  # can be ignored, the view doesn't exist anymore
    except DatabaseError:
        if "could not obtain lock on" in traceback.format_exc():
            recheck_delay = 10
            logger.debug("Retrying view index update in {0} seconds", recheck_delay)
            _set_pending_view_index_update(view_id)

    # check for any pending view index updates and schedule them out of this
    # singleton task to avoid concurrency issues
    _check_for_pending_view_index_updates.s(view_id).apply_async(
        countdown=recheck_delay
    )


def _set_pending_view_index_update(view_id: int):
    cache.set(
        get_auto_index_cache_key(view_id),
        True,
        timeout=settings.AUTO_INDEX_LOCK_EXPIRY * 2,
    )


@app.task(queue="export")
def _check_for_pending_view_index_updates(view_id):
    """
    Checks if there are any pending view index updates and schedules them.
    """

    if cache.delete(get_auto_index_cache_key(view_id)):
        _schedule_view_index_update(view_id)


def _schedule_view_index_update(view_id: int):
    """
    Schedules a view index update for the provided view id. If the view index
    update is already scheduled then just add the view_id in the cache so that
    `update_view_index` will re-schedule itself at the end.

    :param view_id: The id of the view for which the index should be updated.
    """

    # another task has already scheduled the view index update
    if cache.get(get_auto_index_cache_key(view_id)):
        return

    try:
        update_view_index.delay(view_id)
    except DuplicateTaskError:
        # Add the view_id in the cache so that `update_view_index` will
        # re-schedule itself at the end of the currently running task.
        _set_pending_view_index_update(view_id)
    except Exception as exc:  # nosec
        logger.error("Failed to schedule index update because of {e}", e=str(exc))
        traceback.print_exc()


def schedule_view_index_update(view_id: int):
    """
    Schedules a view index update for the provided view id. If the view index
    update is already scheduled then just add the view_id in the cache so that
    `update_view_index` will re-schedule itself at the end.

    :param view_id: The id of the view for which the index should be updated.
    """

    if not settings.AUTO_INDEX_VIEW_ENABLED:
        return

    transaction.on_commit(lambda: _schedule_view_index_update(view_id))


@app.task(queue="export")
def periodic_check_for_views_with_time_sensitive_filters():
    """
    Periodically checks for views that have time-sensitive filters. If a view has a
    time-sensitive filter, this task ensure proper signals are emitted to notify
    subscribers that the view results have changed.
    """

    with transaction.atomic():
        ViewSubscriptionHandler.check_views_with_time_sensitive_filters()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=30),
        periodic_check_for_views_with_time_sensitive_filters.s(),
    )
