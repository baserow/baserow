from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import Signal, receiver

from baserow.contrib.database.fields.models import Field
from baserow.core.models import Workspace
from baserow.core.registries import object_scope_type_registry, subject_type_registry
from baserow.core.signals import workspace_user_updated
from baserow.core.types import ScopeObject, Subject
from baserow.ws.tasks import broadcast_to_users
from baserow_enterprise.role.constants import (
    NO_ACCESS_ROLE_UID,
    NO_ROLE_LOW_PRIORITY_ROLE_UID,
)
from baserow_enterprise.role.models import Role
from baserow_enterprise.tasks import (
    unsubscribe_subject_from_tables_currently_subscribed_to_task,
)

team_created = Signal()
team_updated = Signal()
team_deleted = Signal()
team_restored = Signal()

team_subject_created = Signal()
team_subject_deleted = Signal()
team_subject_restored = Signal()

role_assignment_created = Signal()
role_assignment_updated = Signal()
role_assignment_deleted = Signal()

field_permissions_updated = Signal()


NO_ACCESS_ROLES = [NO_ACCESS_ROLE_UID, NO_ROLE_LOW_PRIORITY_ROLE_UID]


@receiver(workspace_user_updated)
def workspace_user_updated_event(sender, workspace_user, **kwargs):
    """
    This is triggered if a workspace user gets updated.
    If the updated user been assigned `NO_ACCESS` as their permission then the user will
    be unsubscribed from the table they are currently looking at, unless they have other
    permissions that grant them access.
    """

    if workspace_user.permissions in NO_ACCESS_ROLES:
        send_unsubscribe_subject_from_table(
            workspace_user.user, workspace_user.workspace, workspace_user.workspace
        )


@receiver(team_deleted)
def team_deleted_event(sender, team_id, team, user, **kwargs):
    """
    This is triggered if a team gets trashed. This means we need to kick any users
    from tables who only had access via their team.
    """

    send_unsubscribe_subject_from_table(team, team.workspace, team.workspace)


@receiver(role_assignment_updated)
@receiver(role_assignment_created)
def role_assignment_updated_event(
    sender,
    subject: Subject,
    workspace: Workspace,
    scope: ScopeObject,
    role: Role,
    **kwargs,
):
    """
    This is triggered when a role assignment has been deleted in which case we want to
    close any subscriptions the subject might have had to a table page if the new role
    is NO_ACCESS and they therefore don't have access anymore to the scope.

    :param sender: Sender of the signal
    :param subject: Subject that has the association to the users being removed
    :param workspace: The workspace the subject is in
    :param scope: The scope the subject has been removed from
    :param role: The role the subject has been assigned
    """

    if role.uid in NO_ACCESS_ROLES:
        send_unsubscribe_subject_from_table(subject, workspace, scope)


@receiver(role_assignment_deleted)
def role_assignment_deleted_event(
    sender, subject: Subject, workspace: Workspace, scope: ScopeObject, **kwargs
):
    """
    This is triggered when a role assignment has been deleted in which case we want to
    close any subscriptions the subject might have had to a table page.

    :param sender: Sender of the signal
    :param subject: Subject that has the association to the users being removed
    :param workspace: The workspace the subject is in
    :param scope: The scope the subject has been removed from
    """

    send_unsubscribe_subject_from_table(subject, workspace, scope)


def send_unsubscribe_subject_from_table(
    subject: Subject, workspace: Workspace, scope: ScopeObject
):
    subject_id = subject.id
    subject_type_name = subject_type_registry.get_by_model(subject).type
    scope_id = scope.id
    scope_type_name = object_scope_type_registry.get_by_model(scope).type
    workspace_id = workspace.id

    transaction.on_commit(
        lambda: unsubscribe_subject_from_tables_currently_subscribed_to_task.delay(
            subject_id, subject_type_name, scope_id, scope_type_name, workspace_id
        )
    )


@receiver(field_permissions_updated)
def notify_users_about_updated_field_permissions(
    sender,
    user: AbstractUser,
    workspace: Workspace,
    field: Field,
    role: str,
    allow_in_forms: bool,
    **kwargs,
):
    workspace_user_ids = workspace.workspaceuser_set.values_list("user_id", flat=True)

    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            list(workspace_user_ids),
            {
                "type": "field_permissions_updated",
                "workspace_id": workspace.id,
                "field_id": field.id,
                "role": role,
                "allow_in_forms": allow_in_forms,
            },
            getattr(user, "web_socket_id", None),
        )
    )
