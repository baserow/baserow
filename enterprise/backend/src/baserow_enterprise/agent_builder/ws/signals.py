from django.db import transaction
from django.dispatch import receiver

from baserow.core.utils import generate_hash
from baserow.ws.tasks import broadcast_to_group, broadcast_to_permitted_users
from baserow_enterprise.agent_builder.api.serializers import AgentSerializer
from baserow_enterprise.agent_builder.object_scopes import AgentObjectScopeType
from baserow_enterprise.agent_builder.operations import ReadAgentOperationType
from baserow_enterprise.agent_builder.signals import (
    agent_created,
    agent_deleted,
    agent_updated,
    agents_reordered,
)


def _broadcast_agent(agent, user, payload, include_trash=False):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            agent.agent_builder.workspace_id,
            ReadAgentOperationType.type,
            AgentObjectScopeType.type,
            agent.id,
            payload,
            getattr(user, "web_socket_id", None),
            include_trash=include_trash,
        )
    )


@receiver(agent_created)
def agent_created_receiver(sender, agent, user, **kwargs):
    _broadcast_agent(
        agent,
        user,
        {"type": "agent_builder_agent_created", "agent": AgentSerializer(agent).data},
    )


@receiver(agent_updated)
def agent_updated_receiver(sender, agent, user, **kwargs):
    _broadcast_agent(
        agent,
        user,
        {"type": "agent_builder_agent_updated", "agent": AgentSerializer(agent).data},
    )


@receiver(agent_deleted)
def agent_deleted_receiver(sender, agent, user, **kwargs):
    # A deletion also needs to reach read-only clients. Checking the child scope
    # preserves restrictions that would be lost by checking only its application.
    _broadcast_agent(
        agent,
        user,
        {
            "type": "agent_builder_agent_deleted",
            "agent_id": agent.id,
            "agent_builder_id": agent.agent_builder_id,
        },
        include_trash=True,
    )


@receiver(agents_reordered)
def agents_reordered_receiver(sender, agent_builder, order, user, **kwargs):
    payload = {
        "type": "agent_builder_agents_reordered",
        "agent_builder_id": generate_hash(agent_builder.id),
        "order": [generate_hash(agent_id) for agent_id in order],
    }
    transaction.on_commit(
        lambda: broadcast_to_group.delay(
            agent_builder.workspace_id, payload, getattr(user, "web_socket_id", None)
        )
    )
