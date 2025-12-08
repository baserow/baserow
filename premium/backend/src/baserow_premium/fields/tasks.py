from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from baserow_premium.fields.models import AIField, AIFieldScheduledUpdate
from celery_singleton import DuplicateTaskError, Singleton
from loguru import logger

from baserow.config.celery import app
from baserow.core.jobs.handler import JobHandler

PERIODIC_CHECK_MINUTES = 5
PERIODIC_CHECK_TIME_LIMIT = 60 * PERIODIC_CHECK_MINUTES  # 5 minutes.


def has_scheduled_ai_field_updates(field_id: int, until: datetime) -> bool:
    """
    Checks if there are any scheduled AI fields updates.

    :param field_id: ID of the field to check.
    :param until: A max updated_on value
    :return: True, if there are pending updates.
    """

    return AIFieldScheduledUpdate.objects.filter(
        field_id=field_id, updated_on__lte=until
    ).exists()


def get_scheduled_ai_field_updates(field_id: int, until: datetime) -> list[int]:
    """
    Checks if there are any scheduled AI fields updates.

    :param field_id: ID of the field to check.
    :param until: A max updated_on value
    :return: True, if there are pending updates.
    """

    return list(
        AIFieldScheduledUpdate.objects.filter(
            field_id=field_id, updated_on__lte=until
        ).values_list("row_id", flat=True)
    )


def _schedule_generate_ai_value_generation(field_id: int, retry: int):
    """
    Actually schedules AI value generation task.

    :param field_id: AI field id.
    :param retry: The number of retries left for the task.
    """

    generate_scheduled_ai_field_generation.s(
        field_id=field_id, retry=retry
    ).apply_async(countdown=settings.BASEROW_AI_FIELD_AUTO_UPDATE_DEBOUNCE_TIME)


@app.task(
    queue="export",
    base=Singleton,
    unique_on="field_id",
    raise_on_duplicate=True,
    lock_expiry=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
    soft_time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def generate_scheduled_ai_field_generation(field_id: int, retry: int = 3):
    """
    Generates AI field values for rows that have been scheduled for update from AI
    field auto-update feature.

    This is essentially a wrapper around calling `generate_ai_values` with proper
    parameters. This task is a per-field singleton, but also a job, so it can be
    ejected from execution, if there's too many jobs scheduled for the field.

    The job is executed without specific row ids, but with `is_auto_update` flag, which
    will tell the job to get rows to process from the scheduled rows table. If a
    specific scheduled row has been processed successfully, it will be removed from
    the scheduled rows table.

    If the job fails without processing all rows, the remaining scheduled rows will be
    still present in the scheduling table.

    This task will reschedule, if there are any scheduled rows remaining, but only until
    `retry` value is not 0. Each re-execution will decrease the value of `retry`.

    :param field_id: AI field id.
    :param retry: The number of retries left for the task.
    """

    now = timezone.now()

    # this is a task that has been repeated too many times.
    if retry < 1:
        return
    retry -= 1

    jh = JobHandler()
    ai_field = AIField.objects.select_related("ai_auto_update_user").get(id=field_id)

    user = ai_field.ai_auto_update_user

    if row_ids := get_scheduled_ai_field_updates(field_id, now):
        try:
            jh.create_and_start_job(
                user,
                "generate_ai_values",
                field_id=field_id,
                row_ids=row_ids,
                is_auto_update=True,
                sync=True,
            )
        except Exception as e:
            logger.error(f"Job failed: {e}")

    if has_scheduled_ai_field_updates(field_id, now) and retry > 0:
        schedule_ai_field_generation.delay(field_id=field_id, row_ids=[], retry=retry)


@app.task()
def schedule_ai_field_generation(field_id, row_ids, retry: int = 3):
    """
    Populates scheduled rows table for AI field generation.

    :param field_id: AI field id.
    :param row_ids: a list of row ids to be updated.
    :param retry: the number of retries left for the task.
    """

    AIFieldScheduledUpdate.objects.bulk_create(
        [
            AIFieldScheduledUpdate(field_id=field_id, row_id=row_id)
            for row_id in row_ids
        ],
        ignore_conflicts=True,
    )

    try:
        _schedule_generate_ai_value_generation(field_id, retry=retry)
    except DuplicateTaskError:
        pass


@app.task(
    queue="export",
    base=Singleton,
    raise_on_duplicate=False,
    soft_time_limit=PERIODIC_CHECK_TIME_LIMIT,
    time_limit=PERIODIC_CHECK_TIME_LIMIT,
    lock_expiry=PERIODIC_CHECK_TIME_LIMIT,
)
def periodic_reschedule_old_ai_field_generation():
    """
    Removes old rows scheduled for AI field auto-update, and schedules a generation
    task, if there are rows remaining to process.
    """

    cutoff = timezone.now() - timedelta(
        hours=settings.HOURS_UNTIL_TRASH_PERMANENTLY_DELETED
    )

    AIFieldScheduledUpdate.objects.filter(updated_on__lte=cutoff).delete()
    for [field_id] in AIFieldScheduledUpdate.objects.distinct("field_id").values_list(
        "field_id"
    ):
        # we can send an empty list. This will reschedule all pending rows.
        schedule_ai_field_generation(field_id=field_id, row_ids=[])


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=PERIODIC_CHECK_MINUTES),
        periodic_reschedule_old_ai_field_generation.s(),
    )
