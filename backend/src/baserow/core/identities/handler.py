import uuid
from typing import Any

from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from baserow.core.cache import global_cache
from baserow.core.identities.exceptions import IdentityDoesNotExist
from baserow.core.identities.registries import identity_extension_type_registry
from baserow.core.models import User, UserProfile, Workspace, WorkspaceUser
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.identity import is_identity

IDENTITY_LAST_ACTIVE_CACHE_TTL_SECONDS = 60
IDENTITY_LAST_ACTIVE_CACHE_KEY = "identity_{identity_id}_last_active"


class IdentityHandler:
    """Handles identities and their single workspace membership."""

    @staticmethod
    def get_workspace_user(identity: User) -> WorkspaceUser:
        prefetched = getattr(identity, "_prefetched_objects_cache", {})
        memberships = prefetched.get("workspaceuser_set")
        if memberships is None:
            memberships = WorkspaceUser.objects_and_identities.filter(
                user_id=identity.id
            ).select_related("workspace")[:2]
        memberships = list(memberships)
        if not is_identity(identity) or len(memberships) != 1:
            raise IdentityDoesNotExist()
        return memberships[0]

    @classmethod
    def get_workspace(cls, identity: User) -> Workspace:
        return cls.get_workspace_user(identity).workspace

    @classmethod
    def get_role_uid(cls, identity: User) -> str:
        return cls.get_workspace_user(identity).permissions

    def get_queryset(self, workspace: Workspace) -> QuerySet[User]:
        """
        Returns the identities in the workspace with all registered extensions applied.

        :param workspace: The workspace whose identities should be returned.
        :return: A queryset containing the workspace identities.
        """

        queryset = (
            User.objects_and_identities.filter(
                profile__user_type=UserProfile.UserType.IDENTITY,
                profile__trashed=False,
                workspaceuser__workspace=workspace,
            )
            .select_related("profile")
            .prefetch_related(
                Prefetch(
                    "workspaceuser_set",
                    queryset=WorkspaceUser.objects_and_identities.select_related(
                        "workspace"
                    ),
                )
            )
            .order_by("first_name", "id")
        )
        return identity_extension_type_registry.enhance_queryset(queryset, workspace)

    def get_identity(
        self, identity_id: int, base_queryset=None, for_update: bool = False
    ) -> User:
        """
        Returns the identity with the given ID.

        :param identity_id: The ID of the identity to return.
        :param base_queryset: An optional queryset to use when retrieving the identity.
        :param for_update: Lock the identity until the surrounding transaction ends.
        :raises IdentityDoesNotExist: If an identity with the given ID does not exist in
            the queryset.
        :return: The requested identity.
        """

        queryset = (
            base_queryset
            if base_queryset is not None
            else (
                User.objects_and_identities.filter(
                    profile__user_type=UserProfile.UserType.IDENTITY,
                    profile__trashed=False,
                ).select_related("profile")
            )
        )
        if for_update:
            queryset = queryset.select_for_update(of=("self",))
        try:
            identity = queryset.get(id=identity_id)
        except User.DoesNotExist as exc:
            raise IdentityDoesNotExist() from exc
        self.get_workspace_user(identity)
        return identity

    @transaction.atomic
    def create_identity(self, workspace: Workspace, **values: Any) -> User:
        """
        Creates an identity with its single membership in the workspace.

        :param workspace: The workspace in which to create the identity.
        :param values: The identity field values.
        :return: The newly created identity.
        """

        email = f"identity-{uuid.uuid4().hex}@identities.invalid"
        identity = User(
            username=email, email=email, first_name=values["name"], is_active=True
        )
        identity.set_unusable_password()
        identity.save()
        UserProfile.objects.create(
            user=identity,
            user_type=UserProfile.UserType.IDENTITY,
            timezone="UTC",
            email_notification_frequency=UserProfile.EmailNotificationFrequencyOptions.NEVER,
        )
        WorkspaceUser.objects.create(
            user=identity,
            workspace=workspace,
            order=0,
            permissions=values.get("role_uid")
            or identity_extension_type_registry.get_default_role_uid(workspace),
        )
        return identity

    @transaction.atomic
    def update_identity(self, identity: User, **values: Any) -> User:
        """
        Updates the identity's name and workspace role.

        :param identity: The identity to update.
        :param values: The identity field values to update.
        :return: The updated identity.
        """

        membership = self.get_workspace_user(identity)
        if "name" in values:
            identity.first_name = values["name"]
            identity.save(update_fields=["first_name"])
        if "role_uid" in values:
            membership.permissions = values["role_uid"]
            membership.save(update_fields=["permissions", "updated_on"])
        return identity

    def update_last_active(self, identity: User) -> User:
        """
        Sets the identity's last active time at most once per cache interval.

        :param identity: The identity whose last active time should be updated.
        :return: The updated identity.
        """

        def update_timestamp():
            identity.profile.last_active = timezone.now()
            UserProfile.objects_and_trash.filter(user_id=identity.id).update(
                last_active=identity.profile.last_active
            )
            return True

        global_cache.get(
            IDENTITY_LAST_ACTIVE_CACHE_KEY.format(identity_id=identity.id),
            default=update_timestamp,
            timeout=IDENTITY_LAST_ACTIVE_CACHE_TTL_SECONDS,
        )
        return identity

    def delete_identity(self, user, identity: User) -> None:
        """
        Moves an identity to the trash.

        :param user: The user deleting the identity.
        :param identity: The identity to delete.
        """

        TrashHandler.trash(user, self.get_workspace(identity), None, identity.profile)
