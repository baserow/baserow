from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.core.handler import CoreHandler
from baserow.core.identities.exceptions import IdentityRoleDoesNotExist
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.operations import (
    CreateIdentityOperationType,
    DeleteIdentityOperationType,
    ListIdentitiesWorkspaceOperationType,
    UpdateIdentityOperationType,
)
from baserow.core.identities.registries import identity_extension_type_registry
from baserow.core.identities.signals import (
    identity_created,
    identity_deleted,
    identity_updated,
)
from baserow.core.models import User, Workspace


class IdentityService:
    """Provides permission-aware operations for managing workspace identities."""

    def list_identities(self, user: AbstractUser, workspace: Workspace):
        """
        Lists the identities in a workspace that the user is allowed to access.

        :param user: The user requesting the identities.
        :param workspace: The workspace whose identities should be returned.
        :return: A queryset containing the workspace identities.
        """

        CoreHandler().check_permissions(
            user,
            ListIdentitiesWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        return IdentityHandler().get_queryset(workspace)

    @transaction.atomic
    def create_identity(
        self, user: AbstractUser, workspace: Workspace, **values
    ) -> User:
        """
        Creates an identity and its registered extension data in a workspace.

        :param user: The user creating the identity.
        :param workspace: The workspace in which to create the identity.
        :param values: The core and extension field values for the identity.
        :raises IdentityRoleDoesNotExist: If the requested role does not exist.
        :return: The newly created identity with its extension data loaded.
        """

        CoreHandler().check_permissions(
            user,
            CreateIdentityOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        values.setdefault(
            "role_uid", identity_extension_type_registry.get_default_role_uid(workspace)
        )
        if not identity_extension_type_registry.role_uid_exists(
            values["role_uid"], workspace
        ):
            raise IdentityRoleDoesNotExist()
        identity = IdentityHandler().create_identity(workspace, **values)
        for extension in identity_extension_type_registry.get_all():
            extension.create(identity, values, user)
        identity = IdentityHandler().get_identity(
            identity.id, IdentityHandler().get_queryset(workspace)
        )
        identity_created.send(self, user=user, identity=identity)
        return identity

    @transaction.atomic
    def update_identity(self, user: AbstractUser, identity: User, **values) -> User:
        """
        Updates an identity and its registered extension data.

        :param user: The user updating the identity.
        :param identity: The identity to update.
        :param values: The core and extension field values to update.
        :raises IdentityRoleDoesNotExist: If the requested role does not exist.
        :return: The updated identity with its extension data loaded.
        """

        CoreHandler().check_permissions(
            user,
            UpdateIdentityOperationType.type,
            workspace=IdentityHandler.get_workspace(identity),
            context=IdentityHandler.get_workspace(identity),
        )
        # A membership lock can't serialize team edits when the team set is empty.
        identity = IdentityHandler().get_identity(identity.id, for_update=True)
        # A license change can hide the stored role; resubmitting it must keep it.
        if (
            "role_uid" in values
            and values["role_uid"] != IdentityHandler.get_role_uid(identity)
            and not identity_extension_type_registry.role_uid_exists(
                values["role_uid"], IdentityHandler.get_workspace(identity)
            )
        ):
            raise IdentityRoleDoesNotExist()
        original_values = {
            "name": identity.first_name,
            "role_uid": IdentityHandler.get_role_uid(identity),
        }
        IdentityHandler().update_identity(identity, **values)
        for extension in identity_extension_type_registry.get_all():
            extension.update(identity, values, user)
        identity = IdentityHandler().get_identity(
            identity.id,
            IdentityHandler().get_queryset(IdentityHandler.get_workspace(identity)),
        )
        updated_values = {
            "name": identity.first_name,
            "role_uid": IdentityHandler.get_role_uid(identity),
        }
        identity_updated.send(
            self,
            user=user,
            identity=identity,
            updated_fields=[
                key
                for key, value in original_values.items()
                if updated_values[key] != value
            ],
        )
        return identity

    @transaction.atomic
    def delete_identity(self, user: AbstractUser, identity: User) -> None:
        """
        Deletes an identity after preparing all registered extensions for deletion.

        :param user: The user deleting the identity.
        :param identity: The identity to delete.
        """

        CoreHandler().check_permissions(
            user,
            DeleteIdentityOperationType.type,
            workspace=IdentityHandler.get_workspace(identity),
            context=IdentityHandler.get_workspace(identity),
        )
        for extension in identity_extension_type_registry.get_all():
            extension.before_delete(identity, user)
        IdentityHandler().delete_identity(user, identity)
        identity_deleted.send(self, user=user, identity=identity)
