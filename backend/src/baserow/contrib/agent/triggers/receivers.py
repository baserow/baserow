from django.db.models.signals import post_delete
from django.dispatch import receiver

from baserow.contrib.agent.models import AgentTrigger
from baserow.core.services.deferred_deletion import (
    defer_service_deletion,
    is_service_deletion_deferred,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


@receiver(post_delete, sender=AgentTrigger)
def delete_trigger_service(
    sender: type[AgentTrigger], instance: AgentTrigger, **kwargs
) -> None:
    """
    Delete the service with its trigger, also when the agent's deletion cascades
    to the trigger: nothing else holds the service.

    :param sender: The trigger model.
    :param instance: The deleted trigger.
    """

    if is_service_deletion_deferred():
        defer_service_deletion(instance.service_id)
        return
    try:
        service = instance.service
    except Service.DoesNotExist:
        return
    ServiceHandler().delete_service(service.get_type(), service)
