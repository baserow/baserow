from django.conf import settings

from baserow.config.celery import app
from baserow.core.handler import CoreHandler
from baserow_premium.usage.handler import PremiumUsageHandler


@app.task(queue=settings.BASEROW_ROLE_USAGE_QUEUE)
def run_calculate_seats():
    if CoreHandler().get_settings().track_workspace_usage:
        PremiumUsageHandler.calculate_per_workspace_seats_taken()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        settings.BASEROW_SEAT_USAGE_JOB_CRONTAB,
        run_calculate_seats.s(),
    )
