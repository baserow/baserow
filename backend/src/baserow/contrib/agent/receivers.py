from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models import Exists, OuterRef
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from baserow.contrib.agent.last_viewed_types import AgentLastViewedItemType
from baserow.contrib.agent.models import AgentApplication, AgentConversation
from baserow.contrib.agent.signals import agent_loaded
from baserow.contrib.agent.trash_types import AgentConversationTrashableItemType
from baserow.core.identities.import_export import delete_unused_identity_definitions
from baserow.core.last_viewed.handler import LastViewedHandler
from baserow.core.models import TrashEntry

User = get_user_model()


@receiver(agent_loaded)
def agent_loaded_mark_last_viewed(
    sender, agent_id: int, user: AbstractUser, **kwargs
) -> None:
    LastViewedHandler.schedule_mark_viewed(user, AgentLastViewedItemType.type, agent_id)


@receiver(pre_delete, sender=User)
def delete_owned_conversations(sender, instance: AbstractUser, **kwargs) -> None:
    """
    Delete the private conversations nobody else takes part in, and the user's
    trashed private ones, with their trash entries, which would otherwise lose
    their owner and show private titles in everyone's trash.

    :param sender: The user model.
    :param instance: The user being deleted.
    """

    AgentConversation.objects_and_trash.filter(
        owner_user=instance, shared=False, trashed=True
    ).delete()
    memberships = AgentConversation.participants.through.objects.filter(
        agentconversation_id=OuterRef("pk")
    )
    AgentConversation.objects_and_trash.filter(
        Exists(memberships.filter(user=instance)),
        ~Exists(memberships.exclude(user=instance)),
        shared=False,
    ).delete()
    TrashEntry.objects.filter(
        trash_item_type=AgentConversationTrashableItemType.type,
        trash_item_owner=instance,
    ).delete()


@receiver(post_delete, sender=AgentApplication)
def delete_unused_identity_definition(
    sender, instance: AgentApplication, **kwargs
) -> None:
    """
    Delete the definition of the identity a permanently deleted Agent waited for,
    when nothing else waits for it. A trashed Agent keeps it for its restore.

    :param sender: The Agent model.
    :param instance: The Agent being deleted.
    """

    if instance.identity_definition_id is not None:
        delete_unused_identity_definitions([instance.identity_definition_id])
