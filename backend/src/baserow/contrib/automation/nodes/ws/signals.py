import json
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.automation.api.nodes.serializers import (
    AutomationNodeSerializer,
    node_serializer_context,
)
from baserow.contrib.automation.models import AutomationWorkflow
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
    that sends the users who may not see one of them a copy without that data.
    """

    def node_event(context: dict[str, Any]) -> dict[str, Any]:
        return bounded_node_event(
            {
                "type": event_type,
                "node": AutomationNodeSerializer(node, context=context).data,
            }
        )

    workspace_id = node.workflow.automation.workspace_id
    # Shows every table: only sent to the users who may see them.
    event = node_event({})
    web_socket_id = getattr(user, "web_socket_id", None)
    # Without a user, every node that shows a table is hidden.
    hidden_context = node_serializer_context(None, [node])
    table_ids = hidden_context["service_table_access"].table_ids(node)
    if table_ids:
        broadcast_node_event_to_permitted_users.delay(
            workspace_id,
            node.id,
            sorted(table_ids),
            event,
            node_event(hidden_context),
            web_socket_id,
        )
    else:
        broadcast_to_permitted_users.delay(
            workspace_id,
            ReadAutomationNodeOperationType.type,
            AutomationNodeObjectScopeType.type,
            node.id,
            event,
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
