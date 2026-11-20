from typing import Any, Dict, Optional

from baserow.config.celery import app


@app.task(bind=True)
def broadcast_to_workspace_integration_users(
    self,
    workspace_id: int,
    payload: Dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
):
    """
    Broadcasts a realtime event about a workspace integration to everyone who can
    see it: the members who may list the workspace integrations in the workspace
    settings, and those who may list the integrations of at least one application
    of the workspace, since every application offers the workspace integrations.

    :param workspace_id: The workspace of the integration.
    :param payload: The event.
    :param ignore_web_socket_id: The web socket that made the change, which isn't
        sent the event.
    """

    from baserow.core.handler import CoreHandler
    from baserow.core.integrations.operations import (
        ListIntegrationsApplicationOperationType,
        ListIntegrationsWorkspaceOperationType,
    )
    from baserow.core.models import Application, Workspace, WorkspaceUser
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

    # One check per application at most, for the members not permitted yet, so a
    # workspace whose members may all list them is done after the first one.
    applications = Application.objects_without_shared.filter(
        workspace=workspace
    ).order_by("id")
    for application in applications.iterator():
        if not remaining:
            break
        allowed_ids = {
            user.id
            for user in handler.check_permission_for_multiple_actors(
                remaining,
                ListIntegrationsApplicationOperationType.type,
                workspace,
                context=application,
            )
        }
        permitted_ids |= allowed_ids
        remaining = [user for user in remaining if user.id not in allowed_ids]

    if permitted_ids:
        broadcast_to_users(
            list(permitted_ids), payload, ignore_web_socket_id=ignore_web_socket_id
        )
