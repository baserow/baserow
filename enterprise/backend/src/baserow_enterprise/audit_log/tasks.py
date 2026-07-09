from datetime import datetime, timedelta, timezone

from django.conf import settings

from celery_singleton import Singleton

from baserow.config.celery import app

CLEANUP_TIME_LIMIT_SECONDS = (
    settings.BASEROW_ENTERPRISE_AUDIT_LOG_CLEANUP_INTERVAL_MINUTES * 60
)


@app.task(
    bind=True,
    queue="export",
    base=Singleton,
    raise_on_duplicate=False,
    lock_expiry=CLEANUP_TIME_LIMIT_SECONDS,
    soft_time_limit=CLEANUP_TIME_LIMIT_SECONDS,
    time_limit=CLEANUP_TIME_LIMIT_SECONDS,
)
def clean_up_audit_log_entries(self):
    from .handler import AuditLogHandler

    entries_older_than = datetime.now(tz=timezone.utc) - timedelta(
        days=settings.BASEROW_ENTERPRISE_AUDIT_LOG_RETENTION_DAYS
    )
    AuditLogHandler.delete_entries_older_than(entries_older_than)


@app.on_after_finalize.connect
def setup_periodic_audit_log_tasks(sender, **kwargs):
    every = timedelta(
        minutes=settings.BASEROW_ENTERPRISE_AUDIT_LOG_CLEANUP_INTERVAL_MINUTES
    )

    sender.add_periodic_task(every, clean_up_audit_log_entries.s())
