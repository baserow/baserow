from typing import Any, Optional

from baserow.config.celery import app


@app.task(bind=True)
def broadcast_node_event_to_permitted_users(
    self,
    workspace_id: int,
    node_id: int,
    table_ids: list[int],
    event: dict[str, Any],
    hidden_event: dict[str, Any],
    ignore_web_socket_id: Optional[str] = None,
):
    """
    Broadcasts a node event to the users who may read the node. The event shows
    the data of the tables the node uses or reads through other nodes, so the
    users who may not list the fields of one of them are sent the hidden event
    instead.

    :param workspace_id: The workspace of the node.
    :param node_id: The node the event is about.
    :param table_ids: The tables whose data the node shows.
    :param event: The event as a user who may see the table gets it.
    :param hidden_event: The event as a user who may not see the table gets it.
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

    tables = Table.objects_and_trash.select_related("database__workspace").filter(
        id__in=table_ids
    )
    # A table gone in the meantime is checked like one the user may not see.
    allowed = set(readers) if len(tables) == len(set(table_ids)) else set()
    for table in tables:
        allowed &= set(
            CoreHandler().check_permission_for_multiple_actors(
                list(allowed),
                ListFieldsOperationType.type,
                table.database.workspace,
                context=table,
            )
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
            hidden_event,
            ignore_web_socket_id=ignore_web_socket_id,
        )
