import json
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.automation.api.nodes.serializers import AutomationNodeSerializer
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.access import (
    ALLOW_ALL,
    AutomationNodeAccess,
    FixedNodeAccess,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.object_scopes import AutomationNodeObjectScopeType
from baserow.contrib.automation.nodes.operations import (
    ListAutomationNodeOperationType,
    ReadAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.signals import (
    automation_node_created,
    automation_node_deleted,
    automation_node_updated,
)
from baserow.contrib.automation.nodes.ws.tasks import (
    broadcast_node_event_to_permitted_users,
)
from baserow.contrib.automation.workflows.object_scopes import (
    AutomationWorkflowObjectScopeType,
)
from baserow.ws.tasks import broadcast_to_permitted_users

# Channel-layer messages are forwarded verbatim to every websocket. Daphne, which
# serves the dev server, refuses frames over 1 MiB and closes the socket, and the
# replay mechanism then re-sends the same event on reconnect, so one oversized
# event can wedge a client. A node's sample data alone can exceed that (the email
# trigger may carry two 1 MiB bodies), so oversized node events drop the sample
# data and ask the client to refetch the node over HTTP instead. Same bound and
# headroom as the AI provider updates in `baserow.ws.tasks`.
AUTOMATION_NODE_EVENT_MAX_BYTES = 900 * 1024


def bounded_node_event(event: dict) -> dict:
    """
    Returns the event unchanged when it fits comfortably in a websocket frame,
    otherwise a copy whose node carries no sample data and a `requires_refresh`
    flag telling the client to reload the node over HTTP.
    """

    encoded = json.dumps(
        event, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) <= AUTOMATION_NODE_EVENT_MAX_BYTES:
        return event

    node = dict(event["node"])
    service = node.get("service")
    if isinstance(service, dict):
        node["service"] = {**service, "sample_data": None}
    return {**event, "node": node, "requires_refresh": True}


def broadcast_node_event(node: AutomationNode, user: AbstractUser, event_type: str):
    """
    Broadcasts the node to the users who may read it. A node that shows the data
    of tables, its own or those of the nodes it reads, is broadcast with a task
    that sends each user the copy they may see: the full node, the node without
    the data of the nodes it reads, or the node without anything of its table.
    """

    def node_event(access) -> dict[str, Any]:
        context = {"service_table_access": access}
        return bounded_node_event(
            {
                "type": event_type,
                "node": AutomationNodeSerializer(node, context=context).data,
            }
        )

    workspace_id = node.workflow.automation.workspace_id
    web_socket_id = getattr(user, "web_socket_id", None)
    table_id = getattr(node.service.specific, "table_id", None)
    read_table_ids = AutomationNodeAccess(None).read_table_ids(node)
    # Only sent to the users who may see every table.
    event = node_event(ALLOW_ALL)
    if table_id is None and not read_table_ids:
        broadcast_to_permitted_users.delay(
            workspace_id,
            ReadAutomationNodeOperationType.type,
            AutomationNodeObjectScopeType.type,
            node.id,
            event,
            web_socket_id,
        )
        return

    broadcast_node_event_to_permitted_users.delay(
        workspace_id,
        node.id,
        table_id,
        sorted(read_table_ids),
        event,
        node_event(FixedNodeAccess(table=True, data=False)) if read_table_ids else None,
        node_event(FixedNodeAccess(table=False, data=False)) if table_id else None,
        web_socket_id,
    )


@receiver(automation_node_created)
def node_created(sender, node: AutomationNode, user: AbstractUser, **kwargs):
    transaction.on_commit(
        lambda: broadcast_node_event(node, user, "automation_node_created")
    )


@receiver(automation_node_deleted)
def node_deleted(
    sender, workflow: AutomationWorkflow, node_id: int, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            workflow.automation.workspace_id,
            ListAutomationNodeOperationType.type,
            AutomationWorkflowObjectScopeType.type,
            workflow.id,
            {
                "type": "automation_node_deleted",
                "node_id": node_id,
                "workflow_id": workflow.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(automation_node_updated)
def node_updated(sender, node: AutomationNode, user: AbstractUser, **kwargs):
    transaction.on_commit(
        lambda: broadcast_node_event(node, user, "automation_node_updated")
    )
