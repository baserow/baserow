from django.db import transaction

from baserow.config.celery import app
from baserow.contrib.integrations.core.inbound_email_receiver import (
    InboundEmailReceiverError,
)
from baserow.core.services.registries import service_type_registry


@app.task(bind=True, queue="export")
def call_periodic_services_that_are_due(self):
    from baserow.contrib.integrations.core.service_types import CorePeriodicServiceType

    with transaction.atomic():
        service_type_registry.get(
            CorePeriodicServiceType.type
        ).call_periodic_services_that_are_due()


# Retried with exponential backoff (1, 2, 4 ... minutes, capped at an hour)
# while the receiver cannot be used, so a receiver restart or redeploy of a few
# hours does not leave the message behind.
INBOUND_EMAIL_RECEIVER_DELETE_MAX_RETRIES = 8


@app.task(
    bind=True,
    queue="export",
    autoretry_for=(InboundEmailReceiverError,),
    retry_backoff=60,
    retry_backoff_max=60 * 60,
    retry_jitter=True,
    max_retries=INBOUND_EMAIL_RECEIVER_DELETE_MAX_RETRIES,
)
def delete_inbound_email_receiver_message(self, message_id: int):
    """
    Deletes one handed-over message from the bundled inbound mail server, which
    keeps every accepted message forever otherwise. Queued by the inbound email
    webhook for each message it receives. A no-op when inbound email is not
    configured on this instance.
    """

    from baserow.contrib.integrations.core.inbound_email_receiver import (
        delete_receiver_message,
    )

    delete_receiver_message(message_id)
