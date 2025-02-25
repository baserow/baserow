from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.api.user.serializers import PublicUserSerializer
from baserow.api.workspaces.invitations.serializers import (
    UserWorkspaceInvitationSerializer,
)
from baserow.api.workspaces.serializers import (
    WorkspaceSerializer,
    WorkspaceUserSerializer,
    WorkspaceUserWorkspaceSerializer,
)
from baserow.core import signals
from baserow.core.db import specific_iterator
from baserow.core.handler import CoreHandler
from baserow.core.jobs import signals as jobs_signals
from baserow.core.models import Application, WorkspaceUser
from baserow.core.operations import (
    ListApplicationsWorkspaceOperationType,
    ReadApplicationOperationType,
)
from baserow.core.registries import object_scope_type_registry
from baserow.core.user import signals as user_signals
from baserow.core.utils import generate_hash

from .tasks import (
    broadcast_application_created,
    broadcast_to_group,
    broadcast_to_groups,
    broadcast_to_permitted_users,
    broadcast_to_users,
    force_disconnect_users,
)


@receiver(signals.user_updated)
def user_updated(sender, performed_by, user, **kwargs):
    workspace_ids = list(
        WorkspaceUser.objects.filter(user=user).values_list("workspace_id", flat=True)
    )

    transaction.on_commit(
        lambda: broadcast_to_groups.delay(
            workspace_ids,
            {"type": "user_updated", "user": PublicUserSerializer(user).data},
            getattr(performed_by, "web_socket_id", None),
        )
    )


@receiver(signals.user_deleted)
def user_deleted(sender, performed_by, user, **kwargs):
    workspace_ids = list(
        WorkspaceUser.objects.filter(user=user).values_list("workspace_id", flat=True)
    )

    transaction.on_commit(
        lambda: broadcast_to_groups.delay(
            workspace_ids,
            {"type": "user_deleted", "user": PublicUserSerializer(user).data},
        )
    )


@receiver(signals.user_restored)
def user_restored(sender, performed_by, user, **kwargs):
    workspace_ids = list(
        WorkspaceUser.objects.filter(user=user).values_list("workspace_id", flat=True)
    )

    transaction.on_commit(
        lambda: broadcast_to_groups.delay(
            workspace_ids,
            {"type": "user_restored", "user": PublicUserSerializer(user).data},
        )
    )


@receiver(signals.user_permanently_deleted)
def user_permanently_deleted(sender, user_id, workspace_ids, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_groups.delay(
            workspace_ids, {"type": "user_permanently_deleted", "user_id": user_id}
        )
    )


@receiver(signals.workspace_created)
def workspace_created(sender, workspace, user, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_group.delay(
            workspace.id,
            {
                "type": "group_created",
                "workspace": WorkspaceSerializer(workspace).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.workspace_updated)
def workspace_updated(sender, workspace, user, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_group.delay(
            workspace.id,
            {
                "type": "group_updated",
                "workspace_id": workspace.id,
                "workspace": WorkspaceSerializer(workspace).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.workspace_deleted)
def workspace_deleted(
    sender, workspace_id, workspace, workspace_users, user=None, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            [u.id for u in workspace_users],
            {
                "type": "group_deleted",
                "workspace_id": workspace_id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.workspace_user_added)
def workspace_user_added(sender, workspace_user, user, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_group.delay(
            workspace_user.workspace_id,
            {
                "type": "group_user_added",
                "id": workspace_user.id,
                "workspace_id": workspace_user.workspace_id,
                "workspace_user": WorkspaceUserSerializer(workspace_user).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.workspace_user_updated)
def workspace_user_updated(sender, workspace_user, user, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_group.delay(
            workspace_user.workspace_id,
            {
                "type": "group_user_updated",
                "id": workspace_user.id,
                "workspace_id": workspace_user.workspace_id,
                "workspace_user": WorkspaceUserSerializer(workspace_user).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.workspace_user_deleted)
def workspace_user_deleted(sender, workspace_user_id, workspace_user, user, **kwargs):
    def broadcast_to_workspace_and_removed_user():
        payload = {
            "type": "group_user_deleted",
            "id": workspace_user_id,
            "workspace_id": workspace_user.workspace_id,
            "workspace_user": WorkspaceUserSerializer(workspace_user).data,
        }
        broadcast_to_group.delay(
            workspace_user.workspace_id,
            payload,
            getattr(user, "web_socket_id", None),
        )
        broadcast_to_users.delay(
            [workspace_user.user_id],
            payload,
            getattr(user, "web_socket_id", None),
        )

    transaction.on_commit(broadcast_to_workspace_and_removed_user)


@receiver(signals.workspace_restored)
def workspace_restored(sender, workspace_user, user, **kwargs):
    workspaceuser_workspaces = (
        CoreHandler().get_workspaceuser_workspace_queryset().get(id=workspace_user.id)
    )

    applications_qs = workspace_user.workspace.application_set.select_related(
        "content_type", "workspace"
    ).all()
    applications_qs = CoreHandler().filter_queryset(
        workspace_user.user,
        ListApplicationsWorkspaceOperationType.type,
        applications_qs,
        workspace=workspace_user.workspace,
    )
    applications_qs = specific_iterator(applications_qs)
    applications = [
        PolymorphicApplicationResponseSerializer(
            application, context={"user": workspace_user.user}
        ).data
        for application in applications_qs
    ]

    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            [workspace_user.user_id],
            {
                "type": "group_restored",
                "workspace_id": workspace_user.workspace_id,
                "workspace": WorkspaceUserWorkspaceSerializer(
                    workspaceuser_workspaces
                ).data,
                "applications": applications,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.workspaces_reordered)
def workspaces_reordered(sender, workspace_ids, user, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            [user.id],
            {
                "type": "groups_reordered",
                "workspace_ids": workspace_ids,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.application_created)
def application_created(sender, application, user, **kwargs):
    transaction.on_commit(
        lambda: broadcast_application_created.delay(
            application.id, getattr(user, "web_socket_id", None)
        )
    )


@receiver(signals.application_updated)
def application_updated(sender, application: Application, user: AbstractUser, **kwargs):
    scope_type = object_scope_type_registry.get_by_model(application.specific)

    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            application.workspace_id,
            ReadApplicationOperationType.type,
            scope_type.type,
            application.id,
            {
                "type": "application_updated",
                "application_id": application.id,
                "application": PolymorphicApplicationResponseSerializer(
                    application
                ).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.application_deleted)
def application_deleted(sender, application_id, application, user, **kwargs):
    scope_type = object_scope_type_registry.get_by_model(application.specific)

    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            application.workspace_id,
            ReadApplicationOperationType.type,
            scope_type.type,
            application.id,
            {"type": "application_deleted", "application_id": application_id},
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.applications_reordered)
def applications_reordered(sender, workspace, order, user, **kwargs):
    # Hashing all values here to not expose real ids of applications a user might not
    # have access to
    order = [generate_hash(o) for o in order]
    transaction.on_commit(
        lambda: broadcast_to_group.delay(
            workspace.id,
            {
                "type": "applications_reordered",
                "workspace_id": workspace.id,
                "order": order,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(signals.workspace_invitation_updated_or_created)
def notify_workspace_invitation_created(
    sender, invitation, invited_user=None, **kwargs
):
    if invited_user is not None:
        serialized_data = UserWorkspaceInvitationSerializer(invitation).data
        transaction.on_commit(
            lambda: broadcast_to_users.delay(
                [invited_user.id],
                {
                    "type": "workspace_invitation_updated_or_created",
                    "invitation": serialized_data,
                },
            )
        )


@receiver(signals.workspace_invitation_accepted)
def notify_workspace_invitation_accepted(sender, invitation, user, **kwargs):
    # invitation will be deleted on commit, so serialize it now to have the id
    serialized_data = UserWorkspaceInvitationSerializer(invitation).data
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            [user.id],
            {
                "type": "workspace_invitation_accepted",
                "invitation": serialized_data,
            },
        )
    )


@receiver(signals.workspace_invitation_rejected)
def notify_workspace_invitation_rejected(sender, invitation, user, **kwargs):
    # invitation will be deleted on commit, so serialize it now to have the id
    serialized_data = UserWorkspaceInvitationSerializer(invitation).data
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            [user.id],
            {
                "type": "workspace_invitation_rejected",
                "invitation": serialized_data,
            },
        )
    )


@receiver(user_signals.user_password_changed)
def user_password_changed(sender, user, ignore_web_socket_id=None, **kwargs):
    transaction.on_commit(
        lambda: force_disconnect_users.delay(
            [user.id],
            [ignore_web_socket_id],
        )
    )


@receiver(jobs_signals.job_started)
def user_job_started(sender, job, user, **kwargs):
    from baserow.api.jobs.serializers import JobSerializer
    from baserow.core.jobs.registries import job_type_registry

    serializer = job_type_registry.get_serializer(job, JobSerializer)
    broadcast_to_users.delay(
        [user.id],
        {
            "type": "job_started",
            "job": serializer.data,
        },
        getattr(user, "web_socket_id", None),
    )
