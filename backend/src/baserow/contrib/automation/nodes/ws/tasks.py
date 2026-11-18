from typing import Optional

from django.db import DEFAULT_DB_ALIAS

from baserow.config.celery import app
from baserow.config.db_routers import set_db_alias


@app.task(bind=True)
def broadcast_node_event_to_permitted_users(
    self,
    workspace_id: int,
    node_id: int,
    event_type: str,
    ignore_web_socket_id: Optional[str] = None,
):
    """
    Broadcasts a node event to the users who may read the node, each getting the
    copy they may see: the full node, the node without the data of the tables of
    the nodes it reads, or the node without anything of its own table. Only the
    copies someone gets are serialized.

    :param workspace_id: The workspace of the node.
    :param node_id: The node the event is about.
    :param event_type: The type of the event.
    :param ignore_web_socket_id: The web socket that made the change, which
        isn't sent the event.
    """

    from baserow.contrib.automation.api.nodes.serializers import (
        AutomationNodeSerializer,
    )
    from baserow.contrib.automation.nodes.access import (
        ALLOW_ALL,
        AutomationNodeAccess,
        FixedNodeAccess,
        node_table_ids,
    )
    from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
    from baserow.contrib.automation.nodes.operations import (
        ReadAutomationNodeOperationType,
    )
    from baserow.contrib.automation.nodes.ws.signals import bounded_node_event
    from baserow.contrib.integrations.local_baserow.utils import ServiceTableAccess
    from baserow.core.handler import CoreHandler
    from baserow.core.models import Workspace, WorkspaceUser
    from baserow.ws.tasks import broadcast_to_users

    # This task runs after commit; the reads must not lag it.
    set_db_alias(DEFAULT_DB_ALIAS)
    workspace = Workspace.objects.filter(id=workspace_id).first()
    try:
        node = AutomationNodeHandler().get_node(node_id)
    except AutomationNodeDoesNotExist:
        return  # Trashed or deleted in the meantime.
    if workspace is None:
        return

    users = [
        workspace_user.user
        for workspace_user in WorkspaceUser.objects.filter(
            workspace=workspace
        ).select_related("user")
    ]
    readers = CoreHandler().check_permission_for_multiple_actors(
        users, ReadAutomationNodeOperationType.type, workspace, context=node
    )
    if not readers:
        return

    access = AutomationNodeAccess(None)
    tables = ServiceTableAccess(None)
    own_table_ids = node_table_ids(node)
    own_table_readers = tables.users_allowed_on(own_table_ids, readers)
    full_readers = tables.users_allowed_on(
        access.data_table_ids(node), own_table_readers
    )

    groups = {}
    for user in readers:
        if user in full_readers:
            groups.setdefault("full", []).append(user.id)
        elif user in own_table_readers:
            groups.setdefault("data_hidden", []).append(user.id)
        else:
            groups.setdefault("table_hidden", []).append(user.id)
    accesses = {
        "full": ALLOW_ALL,
        "data_hidden": FixedNodeAccess(table=True, data=False),
        "table_hidden": FixedNodeAccess(table=False, data=False),
    }
    for group, user_ids in groups.items():
        context = {"service_table_access": accesses[group]}
        event = bounded_node_event(
            {
                "type": event_type,
                "node": AutomationNodeSerializer(node, context=context).data,
            }
        )
        broadcast_to_users(user_ids, event, ignore_web_socket_id=ignore_web_socket_id)
