from typing import Any, Callable, Dict

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.api.integrations.serializers import IntegrationSerializer
from baserow.core.integrations import signals as integration_signals
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.object_scopes import IntegrationObjectScopeType
from baserow.core.integrations.operations import (
    ListIntegrationsApplicationOperationType,
    ReadIntegrationOperationType,
)
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.tasks import broadcast_to_workspace_integration_users
from baserow.core.models import Application
from baserow.core.object_scopes import ApplicationObjectScopeType
from baserow.ws.tasks import broadcast_to_permitted_users


def _broadcast_on_commit(
    application: Application,
    user: AbstractUser,
    get_payload: Callable[[], Dict[str, Any]],
    operation_type: str,
    scope_name: str,
    scope_id: int,
):
    """
    Broadcasts an event about an integration of the given application once the
    transaction commits, to the users permitted the operation on the scope. The
    event of a workspace integration goes instead to everyone who can see it from
    any application, see `broadcast_to_workspace_integration_users`.

    :param application: The application that holds the integration.
    :param user: The user who made the change, whose web socket is skipped.
    :param get_payload: Returns the event, called when the transaction commits.
    :param operation_type: The operation the recipients are permitted.
    :param scope_name: The scope type the operation is checked on.
    :param scope_id: The id of the scope.
    """

    workspace_id = application.workspace_id
    is_workspace_integration = IntegrationHandler().is_shared_application(application)
    web_socket_id = getattr(user, "web_socket_id", None)

    def broadcast():
        if is_workspace_integration:
            broadcast_to_workspace_integration_users.delay(
                workspace_id, get_payload(), web_socket_id
            )
        else:
            broadcast_to_permitted_users.delay(
                workspace_id,
                operation_type,
                scope_name,
                scope_id,
                get_payload(),
                web_socket_id,
            )

    transaction.on_commit(broadcast)


@receiver(integration_signals.integration_created)
def integration_created(
    sender, integration: Integration, user: AbstractUser, before_id=None, **kwargs
):
    serializer = integration_type_registry.get_serializer(
        integration, IntegrationSerializer
    )
    _broadcast_on_commit(
        integration.application,
        user,
        lambda: {
            "type": "integration_created",
            "integration": serializer.data,
            "before_id": before_id,
        },
        ReadIntegrationOperationType.type,
        IntegrationObjectScopeType.type,
        integration.id,
    )


@receiver(integration_signals.integration_updated)
def integration_updated(sender, integration: Integration, user: AbstractUser, **kwargs):
    serializer = integration_type_registry.get_serializer(
        integration, IntegrationSerializer
    )
    _broadcast_on_commit(
        integration.application,
        user,
        lambda: {
            "type": "integration_updated",
            "integration": serializer.data,
        },
        ReadIntegrationOperationType.type,
        IntegrationObjectScopeType.type,
        integration.id,
    )


@receiver(integration_signals.integration_deleted)
def integration_deleted(
    sender, integration_id: int, application: Application, user: AbstractUser, **kwargs
):
    _broadcast_on_commit(
        application,
        user,
        lambda: {
            "type": "integration_deleted",
            "integration_id": integration_id,
            "application_id": application.id,
        },
        ListIntegrationsApplicationOperationType.type,
        ApplicationObjectScopeType.type,
        application.id,
    )
