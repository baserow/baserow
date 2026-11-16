from typing import Any, Optional

from baserow.config.celery import app

# The service values that name the fields of the service's table.
TABLE_DERIVED_SERVICE_KEYS = ("schema", "context_data", "context_data_schema")


def hide_table_of_node_event(event: dict[str, Any]) -> dict[str, Any]:
    """
    Returns a copy of a node event whose service doesn't show the fields of its
    table, as the node serializer gives it to a user who may not see them.
    """

    node = event["node"]
    service = {
        **node["service"],
        **{key: None for key in TABLE_DERIVED_SERVICE_KEYS},
        "table_accessible": False,
    }
    return {**event, "node": {**node, "service": service}}


@app.task(bind=True)
def broadcast_node_event_to_permitted_users(
    self,
    workspace_id: int,
    node_id: int,
    table_id: int,
    event: dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
):
    """
    Broadcasts a node event to the users who may read the node. The event names
    the fields of the table the node's service uses, so the users who may not
    list those fields are sent a copy without them instead.

    :param workspace_id: The workspace of the node.
    :param node_id: The node the event is about.
    :param table_id: The table the node's service uses.
    :param event: The event as a user who may see the table gets it.
    :param ignore_web_socket_id: The web socket that made the change, which
        isn't sent the event.
    """

    from baserow.contrib.automation.nodes.models import AutomationNode
    from baserow.contrib.automation.nodes.operations import (
        ReadAutomationNodeOperationType,
    )
    from baserow.contrib.database.fields.operations import ListFieldsOperationType
    from baserow.contrib.database.table.models import Table
    from baserow.core.handler import CoreHandler
    from baserow.core.models import Workspace, WorkspaceUser
    from baserow.ws.tasks import broadcast_to_users

    workspace = Workspace.objects.filter(id=workspace_id).first()
    node = AutomationNode.objects_and_trash.filter(id=node_id).first()
    if workspace is None or node is None:
        return  # Trashed or deleted in the meantime.

    users = [
        workspace_user.user
        for workspace_user in WorkspaceUser.objects.filter(
            workspace=workspace
        ).select_related("user")
    ]
    readers = CoreHandler().check_permission_for_multiple_actors(
        users, ReadAutomationNodeOperationType.type, workspace, context=node
    )

    table = Table.objects_and_trash.filter(id=table_id).first()
    allowed = (
        set(
            CoreHandler().check_permission_for_multiple_actors(
                readers, ListFieldsOperationType.type, workspace, context=table
            )
        )
        if table is not None
        else set()
    )

    allowed_ids = [user.id for user in readers if user in allowed]
    hidden_ids = [user.id for user in readers if user not in allowed]
    if allowed_ids:
        broadcast_to_users(
            allowed_ids, event, ignore_web_socket_id=ignore_web_socket_id
        )
    if hidden_ids:
        broadcast_to_users(
            hidden_ids,
            hide_table_of_node_event(event),
            ignore_web_socket_id=ignore_web_socket_id,
        )
