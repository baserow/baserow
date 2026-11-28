from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models import Exists, OuterRef, Q
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from baserow.contrib.agent.constants import AGENT_RUN_TYPE
from baserow.contrib.agent.last_viewed_types import AgentLastViewedItemType
from baserow.contrib.agent.models import AgentApplication, AgentConversation
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.signals import agent_loaded
from baserow.contrib.agent.trash_types import AgentConversationTrashableItemType
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.identities.import_export import delete_unused_identity_definitions
from baserow.core.last_viewed.handler import LastViewedHandler
from baserow.core.models import TrashEntry, WorkspaceUser
from baserow.core.signals import (
    application_deleted,
    workspace_deleted,
    workspace_user_deleted,
)

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


@receiver(workspace_user_deleted)
def leave_conversations_of_left_workspace(
    sender, workspace_user: WorkspaceUser, **kwargs
) -> None:
    # The signal's user is who removed the member, not always the member.
    AgentService().leave_conversations_of_workspace(
        workspace_user.workspace_id, workspace_user.user_id
    )


@receiver(application_deleted)
def stop_replies_of_deleted_agent(sender, application_id: int, **kwargs) -> None:
    """
    Stop the replies a trashed Agent is writing: nobody can stop them anymore.

    :param sender: The sender of the signal.
    :param application_id: The id of the trashed application.
    """

    conversations = AgentConversation.objects_and_trash.filter(agent_id=application_id)
    ChatRunHandler().request_cancel_on_commit(
        AGENT_RUN_TYPE, Q(chat_id__in=conversations.values("id"))
    )


@receiver(workspace_deleted)
def stop_replies_of_deleted_workspace(sender, workspace_id: int, **kwargs) -> None:
    """
    Stop the replies the Agents of a trashed workspace are writing.

    :param sender: The sender of the signal.
    :param workspace_id: The id of the trashed workspace.
    """

    ChatRunHandler().request_cancel_on_commit(
        AGENT_RUN_TYPE, Q(workspace_id=workspace_id)
    )


@receiver(workspace_user_deleted)
def stop_replies_of_left_member(
    sender, workspace_user: WorkspaceUser, **kwargs
) -> None:
    """
    Stop the replies written as a member who left the workspace or was removed.

    :param sender: The sender of the signal.
    :param workspace_user: The deleted membership.
    """

    ChatRunHandler().request_cancel_on_commit(
        AGENT_RUN_TYPE,
        Q(
            workspace_id=workspace_user.workspace_id,
            created_by_id=workspace_user.user_id,
        ),
    )
