from typing import Any, Optional

from baserow.config.celery import app


@app.task(bind=True)
def broadcast_node_event_to_permitted_users(
    self,
    workspace_id: int,
    node_id: int,
    table_id: Optional[int],
    read_table_ids: list[int],
    event: dict[str, Any],
    data_hidden_event: Optional[dict[str, Any]],
    table_hidden_event: Optional[dict[str, Any]],
    ignore_web_socket_id: Optional[str] = None,
):
    """
    Broadcasts a node event to the users who may read the node, each getting the
    copy they may see.

    :param workspace_id: The workspace of the node.
    :param node_id: The node the event is about.
    :param table_id: The table of the node's service, if any.
    :param read_table_ids: The tables of the nodes the node reads.
    :param event: The event for the users who may see every table.
    :param data_hidden_event: The event for the users who may see the node's table
        but not one of the tables it reads.
    :param table_hidden_event: The event for the users who may not see the node's
        table.
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

    wanted = set(read_table_ids) | ({table_id} if table_id is not None else set())
    tables = {
        table.id: table
        for table in Table.objects_and_trash.select_related(
            "database__workspace"
        ).filter(id__in=wanted)
    }

    def allowed_on(table_ids, users):
        # A table gone in the meantime is checked like one they may not see.
        allowed = set(users) if all(i in tables for i in table_ids) else set()
        for read_table_id in table_ids:
            if not allowed:
                break
            table = tables[read_table_id]
            allowed &= set(
                CoreHandler().check_permission_for_multiple_actors(
                    list(allowed),
                    ListFieldsOperationType.type,
                    table.database.workspace,
                    context=table,
                )
            )
        return allowed

    own_table_readers = (
        allowed_on([table_id], readers) if table_id is not None else set(readers)
    )
    full_readers = allowed_on(read_table_ids, own_table_readers)

    groups = {}
    for user in readers:
        if user in full_readers:
            groups.setdefault("full", []).append(user.id)
        elif user in own_table_readers:
            groups.setdefault("data_hidden", []).append(user.id)
        else:
            groups.setdefault("table_hidden", []).append(user.id)
    payloads = {
        "full": event,
        "data_hidden": data_hidden_event,
        "table_hidden": table_hidden_event,
    }
    for group, user_ids in groups.items():
        broadcast_to_users(
            user_ids, payloads[group], ignore_web_socket_id=ignore_web_socket_id
        )
