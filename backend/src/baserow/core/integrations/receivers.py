from typing import Any

from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver

from baserow.core.integrations.models import Integration
from baserow.core.integrations.signals import (
    integration_changed,
    integration_created,
    integration_deleted,
    integration_updated,
)
from baserow.core.models import Application
from baserow.core.signals import application_imported


@receiver(application_imported)
def execute_integration_post_import_hooks(
    sender: Any,
    application: Application,
    user: AbstractUser,
    **kwargs: Any,
) -> None:
    """A receiver to run any post-import hooks for an application."""

    if user is None:
        return

    for integration in application.integrations.all():
        integration.get_type().after_import(user, integration.specific)


@receiver([integration_created, integration_updated, integration_deleted])
def notify_integration_changed(
    sender,
    signal,
    integration: Integration | None = None,
    integration_id: int | None = None,
    application: Application | None = None,
    user: AbstractUser | None = None,
    **kwargs,
):
    """Notify dependent consumers with the same payload for every lifecycle event.

    Deletion supplies an ID and owner instead of an integration instance. Restore
    uses integration_created and promotion uses integration_updated, so both also
    invalidate dependents without additional notifications or database lookups.
    """
    integration_changed.send(
        sender,
        integration_id=integration.id if integration is not None else integration_id,
        application=integration.application if integration is not None else application,
        user=user,
        change_type={
            integration_created: "created",
            integration_updated: "updated",
            integration_deleted: "deleted",
        }[signal],
        integration=integration,
        integration_type=(
            integration.get_type().type
            if integration is not None
            else kwargs.get("integration_type")
        ),
        before_id=kwargs.get("before_id"),
        previous_application=kwargs.get("previous_application"),
    )
