from datetime import datetime, timedelta, timezone

from django.conf import settings

from baserow_premium.fields.models import AIField, AIFieldScheduledUpdate
from celery_singleton import DuplicateTaskError, Singleton
from loguru import logger

from baserow.config.celery import app
from baserow.core.jobs.exceptions import JobCancelled
from baserow.core.jobs.handler import JobHandler

PERIODIC_CHECK_MINUTES = 5
PERIODIC_CHECK_TIME_LIMIT = 60 * PERIODIC_CHECK_MINUTES  # 5 minutes.
DELAY_NEXT_RUN = 60  # 1 minute


def has_scheduled_ai_field_updates(field_id: int) -> bool:
    """
    Checks if there are any scheduled AI fields updates.

    :param field_id: ID of the field to check.
    :return: True, if there are pending updates.
    """

    return AIFieldScheduledUpdate.objects.filter(field_id=field_id).exists()


def get_scheduled_ai_field_updates(field_id: int) -> list[int]:
    """
    Returns a list of rows to process for a field.

    :param field_id: ID of the field to check.
    :return: a list of row ids
    """

    return list(
        AIFieldScheduledUpdate.objects.filter(field_id=field_id)
        .order_by("-updated_on")[: settings.BATCH_ROWS_SIZE_LIMIT]
        .values_list("row_id", flat=True)
    )


def _schedule_generate_ai_value_generation(field_id: int):
    """
    Actually schedules AI value generation task.

    :param field_id: AI field id.
    """

    generate_scheduled_ai_field_generation.s(field_id=field_id).apply_async(
        countdown=settings.BASEROW_AI_FIELD_AUTO_UPDATE_DEBOUNCE_TIME
    )


@app.task(
    queue="export",
    base=Singleton,
    unique_on="field_id",
    raise_on_duplicate=True,
    lock_expiry=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
    soft_time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
    time_limit=settings.CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT,
)
def generate_scheduled_ai_field_generation(field_id: int):
    """
    Generates AI field values for rows that have been scheduled for update from AI
    field auto-update feature.

    This is essentially a wrapper around calling `generate_ai_values` with proper
    parameters. This task is a per-field singleton, but also a job, so it can be
    ejected from execution, if there's too many jobs scheduled for the field.

    The job is executed with specific row ids and `is_auto_update` flag. If a
    specific scheduled row has been processed successfully, it will be removed from
    the scheduled rows table.

    If the job fails without processing all rows, the remaining scheduled rows will be
    still present in the scheduling table, and processed by another task run.

    :param field_id: AI field id.
    """

    jh = JobHandler()

    try:
        ai_field = AIField.objects.select_related("ai_auto_update_user").get(
            id=field_id
        )
    except AIField.DoesNotExist:
        AIFieldScheduledUpdate.objects.filter(field_id=field_id).delete()
        return

    user = ai_field.ai_auto_update_user
    if user is None:
        AIFieldScheduledUpdate.objects.filter(field_id=field_id).delete()
        return

    next_run_delay = 0

    if row_ids := get_scheduled_ai_field_updates(field_id):
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
            next_run_delay = DELAY_NEXT_RUN

    if has_scheduled_ai_field_updates(field_id):
        schedule_ai_field_generation.s(field_id=field_id).apply_async(
            countdown=next_run_delay
        )


@app.task()
def schedule_ai_field_generation(field_id: int, row_ids: list[int] | None = None):
    """
    Populates scheduled rows table for AI field generation.

    If there's no row ids provided, it will just schedule a task. If a row was already
    scheduled, its `updated_on` timestamp will be updated.

    :param field_id: AI field id.
    :param row_ids: a list of row ids to be updated.
    """

    if row_ids:
        AIFieldScheduledUpdate.objects.bulk_create(
            [
                AIFieldScheduledUpdate(field_id=field_id, row_id=row_id)
                for row_id in row_ids
            ],
            update_conflicts=True,
            unique_fields=["field_id", "row_id"],
            update_fields=["updated_on"],
        )

    try:
        _schedule_generate_ai_value_generation(field_id)
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

    cutoff = datetime.now(tz=timezone.utc) - timedelta(
        hours=settings.HOURS_UNTIL_TRASH_PERMANENTLY_DELETED
    )

    AIFieldScheduledUpdate.objects.filter(updated_on__lte=cutoff).delete()
    for field_id in AIFieldScheduledUpdate.objects.distinct("field_id").values_list(
        "field_id", flat=True
    ):
        schedule_ai_field_generation(field_id=field_id, row_ids=[])


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=PERIODIC_CHECK_MINUTES),
        periodic_reschedule_old_ai_field_generation.s(),
    )
