from typing import Any

from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver

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
