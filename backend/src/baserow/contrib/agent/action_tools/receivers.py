from django.db.models.signals import post_delete
from django.dispatch import receiver

from baserow.contrib.agent.models import AgentAction
from baserow.core.services.deferred_deletion import (
    defer_service_deletion,
    is_service_deletion_deferred,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


@receiver(post_delete, sender=AgentAction)
def delete_action_service(sender, instance: AgentAction, **kwargs):
    """Delete the owned service, never the prepared requests held by replies."""

    if is_service_deletion_deferred():
        defer_service_deletion(instance.service_id)
        return
    try:
        service = instance.service
    except Service.DoesNotExist:
        return
    ServiceHandler().delete_service(service.get_type(), service)
