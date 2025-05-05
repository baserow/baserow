from django.conf import settings

from celery_singleton import Singleton

from baserow.config.celery import app
from baserow.core.handler import CoreHandler


@app.task(
    base=Singleton,
    queue=settings.BASEROW_GROUP_STORAGE_USAGE_QUEUE,
    raise_on_duplicate=False,
)
def run_calculate_storage():
    """
    Runs the calculate storage job to keep track of how many mb of memory has been used
    via files by a group
    """

    from baserow.core.usage.handler import UsageHandler

    if CoreHandler().get_settings().track_workspace_usage:
        UsageHandler.calculate_storage_usage()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        settings.BASEROW_STORAGE_USAGE_JOB_CRONTAB,
        run_calculate_storage.s(),
    )
