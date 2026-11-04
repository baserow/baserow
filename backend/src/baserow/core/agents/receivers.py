from django.db.models import QuerySet
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from baserow.core.models import User, UserProfile, Workspace, WorkspaceUser


@receiver(pre_delete, sender=Workspace, dispatch_uid="remember_workspace_agent_users")
def remember_workspace_agent_users(sender, instance, using, **kwargs):
    # Memberships disappear before the workspace's post-delete signal.
    instance._agent_user_ids_to_delete = list(
        WorkspaceUser.objects_and_trash.using(using)
        .agents()
        .filter(workspace_id=instance.id)
        .values_list("user_id", flat=True)
    )


@receiver(post_delete, sender=Workspace, dispatch_uid="delete_workspace_agent_users")
def delete_workspace_agent_users(sender, instance, using, **kwargs):
    User.identities_and_trash.using(using).filter(
        id__in=instance._agent_user_ids_to_delete
    ).delete()


@receiver(post_delete, sender=UserProfile, dispatch_uid="delete_agent_identity")
def delete_agent_identity(sender, instance, using, origin=None, **kwargs):
    if instance.identity_type != UserProfile.IdentityType.AGENT:
        return
    if isinstance(origin, User) or (
        isinstance(origin, QuerySet) and origin.model is User
    ):
        return
    # Profile deletion owns the User, except while that User is already being deleted.
    User.identities_and_trash.using(using).filter(id=instance.user_id).delete()
