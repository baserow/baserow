from django.db.models.signals import post_delete
from django.dispatch import receiver

from baserow.core.models import Agent, User


@receiver(post_delete, sender=Agent, dispatch_uid="delete_agent_user")
def delete_agent_user(sender, instance: Agent, **kwargs) -> None:
    User.objects_and_agents.filter(id=instance.user_id).delete()
