from datetime import datetime, time, timedelta, timezone

from django.conf import settings

from baserow.config.celery import app


@app.task(bind=True, queue="export")
def clean_up_audit_log_entries(self):
    """
    Execute job cleanup for each job types if they need to cleanup something like files
    or old jobs.
    """

    from .handler import AuditLogHandler

    older_than_days = timedelta(
        days=settings.BASEROW_ENTERPRISE_AUDIT_LOG_RETENTION_DAYS
    )
    entries_older_than = datetime.combine(
        datetime.now(tz=timezone.utc) - older_than_days, time.min
    )
    AuditLogHandler.delete_entries_older_than(entries_older_than)


@app.on_after_finalize.connect
def setup_periodic_audit_log_tasks(sender, **kwargs):
    every = timedelta(
        minutes=settings.BASEROW_ENTERPRISE_AUDIT_LOG_CLEANUP_INTERVAL_MINUTES
    )

    sender.add_periodic_task(every, clean_up_audit_log_entries.s())
