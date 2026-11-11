"""Batch service deletion while a parent object is being removed."""

from contextlib import contextmanager
from typing import Generator

from django.conf import settings

from baserow.core.cache import local_cache
from baserow.core.deferred_callbacks import (
    deferred_callback_context,
    register_deferred_callback,
)

from .models import Service

SERVICE_DELETION_CACHE_KEY = "deferred_service_deletion_ids"


def is_service_deletion_deferred() -> bool:
    return local_cache.get_if_cached(SERVICE_DELETION_CACHE_KEY) is not None


def defer_service_deletion(service_id: int) -> None:
    """Adds a service to the active parent-deletion batch."""

    local_cache.get(SERVICE_DELETION_CACHE_KEY, set).add(service_id)


@contextmanager
def deferred_service_deletion_context() -> Generator[None, None, None]:
    """Deletes the services collected during a parent deletion in one query."""

    if not settings.BASEROW_USE_LOCAL_CACHE:
        yield
        return

    if is_service_deletion_deferred():
        yield
        return

    service_ids = local_cache.get(SERVICE_DELETION_CACHE_KEY, set)
    try:
        with deferred_callback_context():

            def delete_deferred_services():
                Service.objects_and_trash.filter(id__in=service_ids).delete()

            register_deferred_callback(delete_deferred_services)
            yield
    finally:
        local_cache.delete(SERVICE_DELETION_CACHE_KEY)
