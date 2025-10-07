from django.db import transaction
from django.utils import timezone

from baserow.config.celery import app
from baserow.core.services.registries import service_type_registry


@app.task(
    bind=True,
    queue="export",
)
def call_periodic_services_that_are_due(self):
    """ """

    from baserow.contrib.integrations.core.service_types import CorePeriodicServiceType

    with transaction.atomic():
        service_type_registry.get(
            CorePeriodicServiceType.type
        ).call_periodic_services_that_are_due(timezone.now())
