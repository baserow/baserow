from django.conf import settings
from django.db import transaction

from celery_singleton import Singleton

from baserow.config.celery import app

CHECK_DUE_TIME_LIMIT = 60
CREATE_SNAPSHOT_TIME_LIMIT = settings.BASEROW_JOB_SOFT_TIME_LIMIT


@app.task(
    bind=True,
    queue="export",
    base=Singleton,
    raise_on_duplicate=False,
    lock_expiry=CHECK_DUE_TIME_LIMIT,
    soft_time_limit=CHECK_DUE_TIME_LIMIT,
    time_limit=CHECK_DUE_TIME_LIMIT,
)
def check_automatic_snapshots_due(self) -> None:
    """
    Periodic task that starts the automatic snapshot schedules that are due.
    """

    from baserow_enterprise.automatic_snapshots.handler import (
        AutomaticSnapshotScheduleHandler,
    )

    with transaction.atomic():
        AutomaticSnapshotScheduleHandler().run_due_schedules()


@app.task(
    bind=True,
    queue=settings.BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_QUEUE_NAME,
    soft_time_limit=CHECK_DUE_TIME_LIMIT,
    time_limit=CHECK_DUE_TIME_LIMIT,
)
def queue_automatic_snapshots(self, schedule_id: int) -> None:
    """
    Queues a snapshot of every application covered by a schedule that is running.

    :param schedule_id: The id of the schedule that is running.
    """

    from baserow_enterprise.automatic_snapshots.handler import (
        AutomaticSnapshotScheduleHandler,
    )

    AutomaticSnapshotScheduleHandler().queue_automatic_snapshots(schedule_id)


@app.task(
    bind=True,
    queue=settings.BASEROW_ENTERPRISE_AUTOMATIC_SNAPSHOTS_QUEUE_NAME,
    base=Singleton,
    unique_on="application_id",
    raise_on_duplicate=False,
    lock_expiry=CREATE_SNAPSHOT_TIME_LIMIT,
    soft_time_limit=CREATE_SNAPSHOT_TIME_LIMIT,
    time_limit=CREATE_SNAPSHOT_TIME_LIMIT + 60,
)
def create_automatic_snapshot(self, schedule_id: int, application_id: int) -> None:
    """
    Creates an automatic snapshot of one application. Only one runs at a time per
    application, so a slow snapshot never overlaps the next run.

    :param schedule_id: The id of the schedule creating the snapshot.
    :param application_id: The id of the application to snapshot.
    """

    from baserow_enterprise.automatic_snapshots.handler import (
        AutomaticSnapshotScheduleHandler,
    )

    AutomaticSnapshotScheduleHandler().create_automatic_snapshot(
        schedule_id, application_id
    )


@app.on_after_finalize.connect
def setup_periodic_automatic_snapshot_tasks(sender, **kwargs) -> None:
    sender.add_periodic_task(
        settings.INTEGRATIONS_PERIODIC_TASK_CRONTAB, check_automatic_snapshots_due.s()
    )
