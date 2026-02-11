from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db.models import Exists, OuterRef, Q

from celery_singleton import DuplicateTaskError, Singleton

from baserow.celery_singleton_backend import SingletonAutoRescheduleFlag
from baserow.config.celery import app
from baserow.core.jobs.handler import JobHandler
from baserow_premium.fields.job_types import GenerateAIValuesJobType
from baserow_premium.fields.models import AIField, AIFieldScheduledUpdate
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler

PERIODIC_CHECK_MINUTES = 5
PERIODIC_CHECK_TIME_LIMIT = 60 * PERIODIC_CHECK_MINUTES


def _get_singleton_autoreschedule_flag(field_id: int) -> SingletonAutoRescheduleFlag:
    return SingletonAutoRescheduleFlag(f"ai_field_generation_lock_{field_id}")


def _schedule_generate_ai_value_generation(field_id: int):
    """
    Actually schedules AI value generation task.

    :param field_id: AI field id.
    """

    try:
        generate_scheduled_ai_field_generation.s(field_id=field_id).apply_async(
            countdown=settings.BASEROW_AI_FIELD_AUTO_UPDATE_DEBOUNCE_TIME
        )
    except DuplicateTaskError:
        flag = _get_singleton_autoreschedule_flag(field_id)
        flag.set()


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
    cancelled.

    The job is executed with `is_auto_update` flag, meaning that when the job runs, it
    will only process rows that were scheduled for update.

    If the job fails without processing all rows, the remaining scheduled rows will be
    still present in the scheduling table, and processed by another task run.

    :param field_id: AI field id.
    """

    jh = JobHandler()

    # Ensure the field still exists and auto-update is still enabled. If not,
    # disabling the auto-update ensures all updates will be removed the next time
    # the periodic task runs.
    try:
        field = AIField.objects.select_related(
            "ai_auto_update_user", "table__database__workspace"
        ).get(id=field_id)
    except AIField.DoesNotExist:
        return

    user = field.ai_auto_update_user
    if not user or not LicenseHandler.user_has_feature(
        PREMIUM, user, field.table.database.workspace
    ):
        field.ai_auto_update = False
        field.ai_auto_update_user = None
        field.save()
        return

    flag = _get_singleton_autoreschedule_flag(field_id)
    flag.clear()

    # Synchronously run the job while keeping the singleton lock, to avoid
    # multiple concurrent job runs for the same field.
    jh.create_and_start_job(
        user,
        GenerateAIValuesJobType.type,
        field_id=field_id,
        is_auto_update=True,
        sync=True,
    )

    if flag.is_set():
        _schedule_generate_ai_value_generation(field_id)


@app.task()
def schedule_ai_field_generation(field_id: int, row_ids: list[int] | None = None):
    """
    Populates scheduled rows table for AI field generation.

    If there's no row ids provided, it will just schedule a task. If a row was already
    scheduled, its `updated_on` timestamp will be updated.

    :param field_id: AI field id.
    :param row_ids: a list of row ids to be updated.
    """

    now = datetime.now(tz=timezone.utc)
    if row_ids:
        AIFieldScheduledUpdate.objects.bulk_create(
            [
                AIFieldScheduledUpdate(field_id=field_id, row_id=row_id, updated_on=now)
                for row_id in row_ids
            ],
            update_conflicts=True,
            unique_fields=["field_id", "row_id"],
            update_fields=["updated_on"],
            batch_size=1000,
        )

    _schedule_generate_ai_value_generation(field_id)


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

    # Delete any old scheduled rows where the associated field no longer exists
    # or the auto_update is disabled
    AIFieldScheduledUpdate.objects.filter(
        Q(updated_on__lte=cutoff)
        | ~Exists(
            AIField.objects.filter(
                id=OuterRef("field_id"),
                ai_auto_update=True,
                ai_auto_update_user__isnull=False,
            )
        )
    ).delete()

    for field_id in AIFieldScheduledUpdate.objects.distinct("field_id").values_list(
        "field_id", flat=True
    ):
        _schedule_generate_ai_value_generation(field_id)


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=PERIODIC_CHECK_MINUTES),
        periodic_reschedule_old_ai_field_generation.s(),
    )
