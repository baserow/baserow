import dataclasses
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    WorkspaceActionScopeType,
)
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.service import IdentityService
from baserow.core.models import User, Workspace


class CreateIdentityActionType(ActionType):
    type = "create_identity"
    description = ActionTypeDescription(
        _("Create identity"),
        _(
            'Identity "%(identity_name)s" (%(identity_id)s) created with role '
            "%(role_uid)s"
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = ["workspace_id", "identity_id", "role_uid"]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        identity_id: int
        identity_name: str
        role_uid: str

    @classmethod
    def do(cls, user: AbstractUser, workspace: Workspace, **values: Any) -> User:
        """
        Creates an identity in the workspace and records who did it.

        :param user: The user creating the identity.
        :param workspace: The workspace in which to create the identity.
        :param values: The core and extension field values for the identity.
        :return: The newly created identity.
        """

        identity = IdentityService().create_identity(user, workspace, **values)
        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id,
                workspace.name,
                identity.id,
                identity.first_name,
                IdentityHandler.get_role_uid(identity),
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return identity

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class UpdateIdentityActionType(ActionType):
    type = "update_identity"
    description = ActionTypeDescription(
        _("Update identity"),
        _(
            'Identity (%(identity_id)s) changed from "%(original_identity_name)s" '
            'with role %(original_role_uid)s to "%(identity_name)s" with role '
            "%(role_uid)s"
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "identity_id",
        "role_uid",
        "original_role_uid",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        identity_id: int
        identity_name: str
        role_uid: str
        original_identity_name: str
        original_role_uid: str

    @classmethod
    def do(cls, user: AbstractUser, identity: User, **values: Any) -> User:
        """
        Updates an identity and, when its name or role changed, records them
        before and after.

        :param user: The user updating the identity.
        :param identity: The identity to update.
        :param values: The core and extension field values to update.
        :return: The updated identity.
        """

        workspace = IdentityHandler.get_workspace(identity)
        updated = IdentityService().update_identity(user, identity, **values)
        if updated.original_values != updated.new_values:
            cls.register_action(
                user=user,
                params=cls.Params(
                    workspace.id,
                    workspace.name,
                    updated.identity.id,
                    updated.new_values["name"],
                    updated.new_values["role_uid"],
                    updated.original_values["name"],
                    updated.original_values["role_uid"],
                ),
                scope=cls.scope(workspace.id),
                workspace=workspace,
            )
        return updated.identity

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class DeleteIdentityActionType(ActionType):
    type = "delete_identity"
    description = ActionTypeDescription(
        _("Delete identity"),
        _('Identity "%(identity_name)s" (%(identity_id)s) deleted'),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = ["workspace_id", "identity_id"]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        identity_id: int
        identity_name: str

    @classmethod
    def do(cls, user: AbstractUser, identity: User) -> None:
        """
        Moves an identity to the trash and records who did it.

        :param user: The user deleting the identity.
        :param identity: The identity to delete.
        """

        workspace = IdentityHandler.get_workspace(identity)
        params = cls.Params(
            workspace.id, workspace.name, identity.id, identity.first_name
        )
        IdentityService().delete_identity(user, identity)
        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)
