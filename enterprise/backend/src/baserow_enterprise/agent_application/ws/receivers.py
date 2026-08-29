from django.dispatch import receiver

from ..realtime import broadcast_agent_definition_updated
from ..signals import agent_definition_updated


@receiver(agent_definition_updated)
def agent_definition_updated_receiver(sender, agent, user=None, **kwargs):
    broadcast_agent_definition_updated(agent)
