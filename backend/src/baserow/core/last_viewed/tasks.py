from datetime import timedelta

from django.conf import settings

from celery_singleton import Singleton

from baserow.config.celery import app
from baserow.ws.tasks import broadcast_to_users


class KeepLockSingleton(Singleton):
    """
    Keeps the lock for the whole update interval after a real write, because the
    database floor makes every run inside that interval a no-op that would still
    cost a task, two queries and a row lock. A run that wrote nothing releases it,
    otherwise a delayed worker or an item that could not be resolved would silence
    the user's next view for a whole interval. Eager runs (tests) share one Redis
    across workers, so they release as before.
    """

    def on_success(self, retval, task_id, args, kwargs):
        if self.request.is_eager or not retval:
            self.release_lock(task_args=args, task_kwargs=kwargs)


# No `autoretry_for` here: a retry re-enters `Singleton.apply_async` while this task
# still holds the lock and would be silently dropped. A failed write is harmless
# because the next view of the same item schedules the task again.
@app.task(
    base=KeepLockSingleton,
    unique_on=["user_id", "item_type", "item_id"],
    raise_on_duplicate=False,
    # Nothing reads the return value; storing it would leave a result key per run
    # and a result subscription in the web worker that published it.
    ignore_result=True,
    # Strictly longer than the database floor, otherwise the run right after the
    # expiry can be a no-op because the previous write happened `countdown` seconds
    # after its lock was taken. Also bounds how long a crashed worker keeps the
    # (user, item) locked.
    lock_expiry=(
        settings.BASEROW_LAST_VIEWED_UPDATE_INTERVAL_SECONDS
        + settings.BASEROW_LAST_VIEWED_DEBOUNCE_SECONDS
    ),
)
def mark_item_viewed(user_id: int, item_type: str, item_id: int) -> bool:
    """
    Stores that the user viewed the item and, when the stored value changed, tells
    the user's connected clients about it.

    :param user_id: The id of the user that opened the item.
    :param item_type: The type of a registered `LastViewedItemType`.
    :param item_id: The id of the item that was opened.
    :return: Whether a value was written, which decides if the lock is kept.
    """

    # The handler imports this module for `schedule_mark_viewed`.
    from .handler import LastViewedHandler

    update = LastViewedHandler.mark_viewed(user_id, item_type, item_id)
    if update is None:
        return False

    # Sent to the user rather than the workspace: the value is personal, and it
    # keeps every open tab in sync without any page-specific frontend hooks.
    broadcast_to_users.apply(
        (
            [user_id],
            {
                "type": "last_viewed_updated",
                "item_type": item_type,
                "item_id": item_id,
                "application_id": update.application_id,
                "workspace_id": update.workspace_id,
                "last_viewed": LastViewedHandler.serialize_last_viewed(
                    update.last_viewed
                ),
            },
        )
    )
    return True


@app.task(bind=True, queue="export")
def clean_up_stale_last_viewed_items(self):
    from .handler import LastViewedHandler

    LastViewedHandler.delete_stale_items()


@app.on_after_finalize.connect
def setup_periodic_last_viewed_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=settings.BASEROW_LAST_VIEWED_CLEANUP_INTERVAL_MINUTES),
        clean_up_stale_last_viewed_items.s(),
    )
