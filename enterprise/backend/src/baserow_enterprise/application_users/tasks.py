from datetime import timedelta

from baserow.config.celery import app


@app.task(bind=True, queue="export")
def check_application_user_limits(self):
    """
    Notifies the admins of every workspace that approaches or exceeds its application
    user limit, and keeps the over limit state that drives the login enforcement grace
    period up to date.

    This deliberately runs on its own schedule instead of hanging off the periodic
    license check: every install has an application user limit, including unlicensed
    ones, and the license check doesn't run at all when there are no licenses.
    """

    from baserow_enterprise.application_users.usage import (
        notify_workspaces_approaching_application_user_limit,
    )

    notify_workspaces_approaching_application_user_limit()


@app.on_after_finalize.connect
def setup_periodic_application_user_tasks(sender, **kwargs):
    sender.add_periodic_task(timedelta(hours=1), check_application_user_limits.s())
