# TODO:
# 1. Add tasks that mark for deletion:
#    - all ImportExportResources with is_valid=False
#    - all ImportExportResources with is_valid=True and are older than 5 days
# 2. Add a task that periodically delete (once per hour) all ImportExportResources
#   that are marked for deletion.
# 3. Add tests to make sure that the tasks are working as expected.

from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from celery_singleton import Singleton

from baserow.config.celery import app
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import ImportExportResource

DELETE_MARKED_IMPORT_EXPORT_RESOURCES_TIME_LIMIT = (
    60 * settings.BASEROW_IMPORT_EXPORT_RESOURCE_CLEANUP_INTERVAL_MINUTES
)


@app.task(bind=True, queue="export")
def mark_import_export_resources_for_deletion(
    self,
    older_than_days: int = settings.BASEROW_IMPORT_EXPORT_RESOURCE_REMOVAL_AFTER_DAYS,
):
    """
    Marks all ImportExportResources that are invalid or are older than 5 days for
    deletion.

    :param older_than_days: The number of days that the ImportExportResources should
        be older than to be marked for deletion.
    """

    cutoff_time = timezone.now() - timedelta(days=older_than_days)

    ImportExportResource.objects.filter(
        Q(is_valid=False) | Q(is_valid=True, created_on__lte=cutoff_time)
    ).update(marked_for_deletion=True)


@app.task(
    base=Singleton,
    bind=True,
    queue="export",
    soft_time_limit=DELETE_MARKED_IMPORT_EXPORT_RESOURCES_TIME_LIMIT,
    time_limit=DELETE_MARKED_IMPORT_EXPORT_RESOURCES_TIME_LIMIT,
    lock_expiry=DELETE_MARKED_IMPORT_EXPORT_RESOURCES_TIME_LIMIT,
)
def delete_marked_import_export_resources(self):
    """
    Deletes all ImportExportResources that are marked for deletion.
    """

    ImportExportHandler().permanently_delete_trashed_resources()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(
            minutes=settings.BASEROW_IMPORT_EXPORT_RESOURCE_CLEANUP_INTERVAL_MINUTES
        ),
        mark_import_export_resources_for_deletion.s(),
    )
    sender.add_periodic_task(
        timedelta(
            minutes=settings.BASEROW_IMPORT_EXPORT_RESOURCE_CLEANUP_INTERVAL_MINUTES
        ),
        delete_marked_import_export_resources.s(),
    )
