from django.db.models import QuerySet
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from baserow.core.models import User, UserProfile, Workspace, WorkspaceUser


@receiver(
    pre_delete, sender=Workspace, dispatch_uid="remember_workspace_identity_users"
)
def remember_workspace_identity_users(sender, instance, using, **kwargs):
    # Memberships disappear before the workspace's post-delete signal.
    instance._identity_user_ids_to_delete = list(
        WorkspaceUser.objects_and_identities.using(using)
        .filter(
            workspace_id=instance.id,
            user__profile__user_type=UserProfile.UserType.IDENTITY,
        )
        .values_list("user_id", flat=True)
    )


@receiver(post_delete, sender=Workspace, dispatch_uid="delete_workspace_identity_users")
def delete_workspace_identity_users(sender, instance, using, **kwargs):
    User.objects_and_identities.using(using).filter(
        id__in=instance._identity_user_ids_to_delete
    ).delete()


@receiver(post_delete, sender=UserProfile, dispatch_uid="delete_identity_user")
def delete_identity_user(sender, instance, using, origin=None, **kwargs):
    if instance.user_type != UserProfile.UserType.IDENTITY:
        return
    if isinstance(origin, User) or (
        isinstance(origin, QuerySet) and origin.model is User
    ):
        return
    # Profile deletion owns the User, except while that User is already being deleted.
    User.objects_and_identities.using(using).filter(id=instance.user_id).delete()
