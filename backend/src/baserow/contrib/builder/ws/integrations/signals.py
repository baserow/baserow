from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.api.integrations.serializers import IntegrationSerializer
from baserow.core.integrations import signals as integration_signals
from baserow.core.integrations.models import Integration
from baserow.core.integrations.object_scopes import IntegrationObjectScopeType
from baserow.core.integrations.operations import (
    ListIntegrationsApplicationOperationType,
    ReadIntegrationOperationType,
)
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.models import Application
from baserow.core.object_scopes import ApplicationObjectScopeType
from baserow.ws.tasks import broadcast_to_permitted_users


@receiver(integration_signals.integration_created)
def integration_created(
    sender, integration: Integration, user: AbstractUser, before_id=None, **kwargs
):
    serializer = integration_type_registry.get_serializer(
        integration, IntegrationSerializer
    )
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            integration.application.workspace_id,
            ReadIntegrationOperationType.type,
            IntegrationObjectScopeType.type,
            integration.id,
            {
                "type": "integration_created",
                "integration": serializer.data,
                "before_id": before_id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(integration_signals.integration_updated)
def integration_updated(sender, integration: Integration, user: AbstractUser, **kwargs):
    serializer = integration_type_registry.get_serializer(
        integration, IntegrationSerializer
    )
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            integration.application.workspace_id,
            ReadIntegrationOperationType.type,
            IntegrationObjectScopeType.type,
            integration.id,
            {
                "type": "integration_updated",
                "integration": serializer.data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(integration_signals.integration_deleted)
def integration_deleted(
    sender, integration_id: int, application: Application, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            application.workspace_id,
            ListIntegrationsApplicationOperationType.type,
            ApplicationObjectScopeType.type,
            application.id,
            {
                "type": "integration_deleted",
                "integration_id": integration_id,
                "application_id": application.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )
