from typing import Any, Dict, Optional

from baserow.config.celery import app


@app.task(bind=True)
def broadcast_to_workspace_integration_users(
    self,
    workspace_id: int,
    payload: Dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
    integration_type: Optional[str] = None,
):
    """
    Broadcasts a realtime event about a workspace integration to everyone who can
    see it: the members who may list the workspace integrations in the workspace
    settings, and those who may list the integrations of at least one application
    of the workspace that can use an integration of its type, since those
    applications offer it, see `ApplicationType.can_use_workspace_integration_type`.

    :param workspace_id: The workspace of the integration.
    :param payload: The event.
    :param ignore_web_socket_id: The web socket that made the change, which isn't
        sent the event.
    :param integration_type: The type of the integration. Without it, every
        application of the workspace counts.
    """

    from django.contrib.contenttypes.models import ContentType

    from baserow.core.handler import CoreHandler
    from baserow.core.integrations.operations import (
        ListIntegrationsApplicationOperationType,
        ListIntegrationsWorkspaceOperationType,
    )
    from baserow.core.integrations.registries import integration_type_registry
    from baserow.core.models import Application, Workspace, WorkspaceUser
    from baserow.core.registries import application_type_registry
    from baserow.core.types import PermissionCheck
    from baserow.ws.tasks import broadcast_to_users

    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        return  # trashed in the meantime

    handler = CoreHandler()
    members = [
        workspace_user.user
        for workspace_user in WorkspaceUser.objects.filter(
            workspace=workspace
        ).select_related("user")
    ]

    permitted = handler.check_permission_for_multiple_actors(
        members,
        ListIntegrationsWorkspaceOperationType.type,
        workspace,
        context=workspace,
    )
    permitted_ids = {user.id for user in permitted}
    remaining = [user for user in members if user.id not in permitted_ids]

    # The members not permitted yet are checked on every application in one call, so
    # that the queries don't grow with the number of applications.
    if remaining:
        applications = Application.objects_without_shared.filter(workspace=workspace)
        if integration_type is not None:
            integration_type_instance = integration_type_registry.get(integration_type)
            using_models = [
                application_type.model_class
                for application_type in application_type_registry.get_all()
                if application_type.can_use_workspace_integration_type(
                    integration_type_instance
                )
            ]
            applications = applications.filter(
                content_type__in=list(
                    ContentType.objects.get_for_models(*using_models).values()
                )
            )
        # The permission check walks from each application up to its workspace.
        checks = [
            PermissionCheck(
                user, ListIntegrationsApplicationOperationType.type, application
            )
            for application in applications.select_related("workspace")
            for user in remaining
        ]
        results = handler.check_multiple_permissions(checks, workspace)
        permitted_ids |= {
            check.actor.id for check, allowed in results.items() if allowed is True
        }

    if permitted_ids:
        broadcast_to_users(
            list(permitted_ids), payload, ignore_web_socket_id=ignore_web_socket_id
        )
