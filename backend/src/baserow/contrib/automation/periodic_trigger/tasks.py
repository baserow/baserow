from datetime import timedelta

from django.db import transaction

from baserow.config.celery import app


@app.task(
    bind=True,
    queue="export",
)
def call_periodic_triggers_that_are_due(self):
    """
    Celery task that calls the handler to execute periodic triggers that are due. This
    must always run every minute to ensure we're able to accommodate the minimum
    internal, which is every minute. It's okay if this task runs multiple times because
    is locks the services that are going to be triggered, and will skip the ones that
    are locked.
    """

    from baserow.contrib.automation.periodic_trigger.handler import (
        PeriodicTriggerHandler,
    )

    with transaction.atomic():
        PeriodicTriggerHandler().call_periodic_triggers_that_are_due()


@app.on_after_finalize.connect
def setup_periodic_trigger_tasks(sender, **kwargs):
    every = timedelta(seconds=20)
    sender.add_periodic_task(every, call_periodic_triggers_that_are_due.s())
