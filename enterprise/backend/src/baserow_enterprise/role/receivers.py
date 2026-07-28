from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from baserow.core.models import Workspace, WorkspaceUser
from baserow.core.registries import subject_type_registry
from baserow.core.signals import permissions_updated, workspace_user_updated
from baserow.core.types import Subject
from baserow.ws.tasks import broadcast_to_users
from baserow_enterprise.signals import (
    role_assignment_created,
    role_assignment_deleted,
    role_assignment_updated,
    team_deleted,
    team_restored,
)
from baserow_enterprise.teams.models import Team

User = get_user_model()


@receiver(role_assignment_updated)
@receiver(role_assignment_created)
@receiver(role_assignment_deleted)
def send_permissions_updated_when_role_assignment_updated(
    sender, subject: Subject, workspace: Workspace, **kwargs
):
    permissions_updated.send(sender, subject=subject, workspace=workspace)


@receiver(workspace_user_updated)
def send_permissions_updated_when_workspace_user_updated(
    sender, workspace_user: WorkspaceUser, permissions_before: str, **kwargs
):
    if permissions_before != workspace_user.permissions:
        permissions_updated.send(
            sender, subject=workspace_user.user, workspace=workspace_user.workspace
        )


@receiver(team_deleted)
@receiver(team_restored)
def send_permissions_updated_when_team_was_deleted(sender, team: Team, **kwargs):
    permissions_updated.send(sender, subject=team, workspace=team.workspace)


@receiver(permissions_updated)
def notify_users_about_updated_permissions(
    sender, subject: Subject, workspace: Workspace, **kwargs
):
    subject_type = subject_type_registry.get_by_model(subject)
    associated_users = subject_type.get_users_included_in_subject(subject)
    associated_user_ids = [user.id for user in associated_users]

    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            associated_user_ids,
            {
                "type": "permissions_updated",
                "workspace_id": workspace.id,
            },
        )
    )


def cascade_subject_delete(sender, instance, **kwargs):
    """
    Delete role assignments linked to deleted subjects.
    """

    from .models import RoleAssignment

    subject_ct = ContentType.objects.get_for_model(instance)
    RoleAssignment.objects.filter(
        subject_id=instance.id, subject_type=subject_ct
    ).delete()


def cascade_workspace_user_delete(sender, instance, **kwargs):
    """
    Delete role assignments linked user to deleted WorkspaceUser.
    """

    from .models import RoleAssignment

    user_id = instance.user_id
    workspace_id = instance.workspace_id
    user_ct = ContentType.objects.get_for_model(User)
    RoleAssignment.objects.filter(
        subject_id=user_id, subject_type=user_ct, workspace_id=workspace_id
    ).delete()


def cascade_scope_delete(sender, instance, **kwargs):
    """
    Delete role assignments linked to deleted scope.
    """

    from .models import RoleAssignment

    scope_ct = ContentType.objects.get_for_model(instance)
    RoleAssignment.objects.filter(scope_id=instance.id, scope_type=scope_ct).delete()


def connect_to_post_delete_signals_to_cascade_deletion_to_role_assignments():
    """
    Connect to post_delete signal of all role_assignment generic foreign key to delete
    all related role_assignments.
    """

    from baserow.contrib.database.fields.models import Field
    from baserow.core.models import WorkspaceUser
    from baserow.core.registries import (
        object_scope_type_registry,
        subject_type_registry,
    )
    from baserow_enterprise.role.constants import ROLE_ASSIGNABLE_OBJECT_MAP

    # Add the subject handler
    for subject_type in subject_type_registry.get_all():
        post_delete.connect(cascade_subject_delete, subject_type.model_class)

    # Add the WorkspaceUser handler
    post_delete.connect(cascade_workspace_user_delete, WorkspaceUser)

    # Add the scope handler
    for role_assignable_object_type in ROLE_ASSIGNABLE_OBJECT_MAP.keys():
        scope_type = object_scope_type_registry.get(role_assignable_object_type)
        post_delete.connect(cascade_scope_delete, scope_type.model_class)

    # Field permission subjects are stored as internal field-scoped role assignments.
    # Fields are intentionally not general role-assignable objects, so register their
    # cascade explicitly.
    post_delete.connect(cascade_scope_delete, Field)
