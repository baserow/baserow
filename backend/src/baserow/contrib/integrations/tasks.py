from datetime import timedelta

from django.conf import settings
from django.db import transaction

from baserow.config.celery import app
from baserow.core.services.registries import service_type_registry


@app.task(bind=True, queue="export")
def call_periodic_services_that_are_due(self):
    from baserow.contrib.integrations.core.service_types import CorePeriodicServiceType

    with transaction.atomic():
        service_type_registry.get(
            CorePeriodicServiceType.type
        ).call_periodic_services_that_are_due()


@app.task(bind=True, queue="export")
def sweep_inbound_email_receiver(self):
    """
    Deletes handed-over messages from the bundled inbound mail server, which
    keeps them forever otherwise. A no-op when inbound email is not configured.
    """

    from baserow.contrib.integrations.core.inbound_email_receiver import (
        sweep_inbound_email_receiver as sweep,
    )

    sweep()


@app.on_after_finalize.connect
def setup_inbound_email_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=settings.INBOUND_EMAIL_SWEEP_INTERVAL_MINUTES),
        sweep_inbound_email_receiver.s(),
        name="inbound-email-receiver-sweep",
    )
