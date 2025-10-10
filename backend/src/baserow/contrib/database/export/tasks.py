from datetime import timedelta

from django.conf import settings

from baserow.config.celery import app

EXPORT_SOFT_TIME_LIMIT = 60 * 60
EXPORT_TIME_LIMIT = EXPORT_SOFT_TIME_LIMIT + 60


# noinspection PyUnusedLocal
@app.task(
    bind=True,
    soft_time_limit=EXPORT_SOFT_TIME_LIMIT,
    time_limit=EXPORT_TIME_LIMIT,
)
def run_export_job(self, job_id):
    """
    Runs the export for a given job. Configured in base.py to run on a separate queue
    to prevent starving regular websocket jobs.
    """

    from baserow.contrib.database.export.handler import ExportHandler
    from baserow.contrib.database.export.models import ExportJob

    job = ExportJob.objects.get(id=job_id)
    ExportHandler.run_export_job(job)


# noinspection PyUnusedLocal
@app.task(
    bind=True,
)
def clean_up_old_jobs(self):
    """
    Looks for any old jobs and cleans them up at the configured interval set below.
    Runs on the export celery queue.
    """

    from baserow.contrib.database.export.handler import ExportHandler

    ExportHandler.clean_up_old_jobs()


# noinspection PyUnusedLocal
@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=settings.EXPORT_CLEANUP_INTERVAL_MINUTES),
        clean_up_old_jobs.s(),
    )
