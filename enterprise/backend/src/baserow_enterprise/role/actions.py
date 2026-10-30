import dataclasses
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import RootActionScopeType, WorkspaceActionScopeType
from baserow.core.models import Workspace
from baserow.core.registries import object_scope_type_registry, subject_type_registry
from baserow.core.types import ScopeObject
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.types import NewRoleAssignment

from .models import Role, RoleAssignment, WorkspaceScopedInvitation
from .types import AssignmentTuple


class BatchAssignRoleActionType(ActionType):
    """
    Not undoable, like the workspace and scoped invitations it is used alongside:
    undoing it would add or remove someone's access without asking.
    """

    type = "batch_assign_role"
    description = ActionTypeDescription(
        _("Assign multiple roles"),
        _("Multiple roles have been assigned"),
    )
    long_desc_if_one_assignment = _(
        'Role %(role_uid)s assigned to subject type "%(subject_type_name)s" (%(subject_id)s) '
        'on scope type "%(scope_type_name)s" (%(scope_id)s).'
    )
    analytics_params = [
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        assignments: List[AssignmentTuple]

    @classmethod
    def get_long_description(cls, params_dict: Dict[str, Any], *args, **kwargs) -> str:
        if len(params_dict["assignments"]) == 1:
            assignment = AssignmentTuple(*params_dict["assignments"][0])._asdict()
            try:
                subject_type = subject_type_registry.get(
                    assignment["subject_type_name"]
                )
            except subject_type_registry.does_not_exist_exception_class:
                pass
            else:
                assignment["subject_type_name"] = subject_type.get_type_display_name()
            return cls.long_desc_if_one_assignment % assignment
        else:
            return super().get_long_description(params_dict, *args, **kwargs)

    @classmethod
    def do(
        cls,
        user,
        new_role_assignments: List[NewRoleAssignment],
        workspace: Workspace,
    ) -> List[Optional[RoleAssignment]]:
        """
        Apply the given role assignments in an action.

        :param user: The user who do the action.
        :param new_role_assignments: A list a new role assignments. A role assignment is
            a triplet of (subject, role, scope).
        :return: The result role assignment object related to the new_role_assignment.
            If the role has been deleted the value is None instead of a role assignment.
        """

        role_assignment_handler = RoleAssignmentHandler()

        user_and_scope_set = {
            (subject, scope) for subject, _, scope in new_role_assignments
        }

        # get current roles to be able to record them alongside with the action
        previous_roles = role_assignment_handler.get_current_role_assignments(
            workspace, user_and_scope_set
        )

        role_assignments = role_assignment_handler.assign_role_batch_for_user(
            user, workspace, new_role_assignments
        )

        # Build the list of assignment tuples we want to save in the action
        param_assignments = []
        for subject, role, scope in new_role_assignments:
            subject_type = subject_type_registry.get_by_model(subject)
            scope_type = object_scope_type_registry.get_by_model(scope)
            previous_role_assignment = previous_roles[(subject, scope)]
            previous_role_uid = (
                previous_role_assignment.role.uid if previous_role_assignment else None
            )

            param_assignments.append(
                AssignmentTuple(
                    subject_type.type,
                    subject.id,
                    previous_role_uid,
                    role.uid if role else None,
                    scope_type.type,
                    scope.id,
                )
            )

        cls.register_action(
            user=user,
            params=cls.Params(workspace.id, param_assignments),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )

        return role_assignments

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class CreateScopedInvitationActionType(ActionType):
    type = "create_scoped_invitation"
    description = ActionTypeDescription(
        _("Create scoped invitation"),
        _(
            'Invitation created for "%(email)s" to join "%(group_name)s" '
            '(%(group_id)s) as %(role_uid)s on "%(scope_type_name)s" '
            "(%(scope_id)s)."
        ),
    )
    analytics_params = [
        "workspace_id",
        "role_uid",
        "scope_type_name",
    ]

    @dataclasses.dataclass
    class Params:
        email: str
        role_uid: str
        scope_type_name: str
        scope_id: int
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        email: str,
        role: Role,
        scope: ScopeObject,
    ) -> WorkspaceScopedInvitation:
        """
        Invites an email address to one scope of the workspace and sends the
        invitation email. Look into
        `RoleAssignmentHandler.create_scoped_invitation` for further details.
        """

        scoped_invitation = RoleAssignmentHandler().create_scoped_invitation(
            user, workspace, email, role, scope
        )
        scope_type = object_scope_type_registry.get_by_model(scope)

        cls.register_action(
            user=user,
            params=cls.Params(
                scoped_invitation.invitation.email,
                role.uid,
                scope_type.type,
                scope.id,
                workspace.id,
                workspace.name,
            ),
            scope=cls.scope(),
            workspace=workspace,
        )
        return scoped_invitation

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class UpdateScopedInvitationActionType(ActionType):
    type = "update_scoped_invitation"
    description = ActionTypeDescription(
        _("Update scoped invitation"),
        _(
            'Invitation (%(invitation_id)s) role for "%(email)s" on '
            '"%(scope_type_name)s" (%(scope_id)s) in "%(group_name)s" '
            "(%(group_id)s) changed from %(original_role_uid)s to %(role_uid)s."
        ),
    )
    analytics_params = [
        "workspace_id",
        "role_uid",
        "original_role_uid",
        "scope_type_name",
    ]

    @dataclasses.dataclass
    class Params:
        scoped_invitation_id: int
        invitation_id: int
        email: str
        role_uid: str
        original_role_uid: str
        scope_type_name: str
        scope_id: int
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        scoped_invitation: WorkspaceScopedInvitation,
        role: Role,
    ) -> WorkspaceScopedInvitation:
        """
        Changes the role a pending invitation grants on its scope. Look into
        `RoleAssignmentHandler.update_scoped_invitation` for further details.
        """

        workspace = scoped_invitation.invitation.workspace
        original_role_uid = scoped_invitation.role.uid
        scoped_invitation = RoleAssignmentHandler().update_scoped_invitation(
            user, scoped_invitation, role
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                scoped_invitation.id,
                scoped_invitation.invitation_id,
                scoped_invitation.invitation.email,
                role.uid,
                original_role_uid,
                _scope_type_name(scoped_invitation),
                scoped_invitation.scope_id,
                workspace.id,
                workspace.name,
            ),
            scope=cls.scope(),
            workspace=workspace,
        )
        return scoped_invitation

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class DeleteScopedInvitationActionType(ActionType):
    type = "delete_scoped_invitation"
    description = ActionTypeDescription(
        _("Delete scoped invitation"),
        _(
            'Invitation (%(invitation_id)s) role %(role_uid)s for "%(email)s" on '
            '"%(scope_type_name)s" (%(scope_id)s) in "%(group_name)s" '
            "(%(group_id)s) revoked."
        ),
    )
    analytics_params = [
        "workspace_id",
        "role_uid",
        "scope_type_name",
    ]

    @dataclasses.dataclass
    class Params:
        scoped_invitation_id: int
        invitation_id: int
        email: str
        role_uid: str
        scope_type_name: str
        scope_id: int
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(cls, user: AbstractUser, scoped_invitation: WorkspaceScopedInvitation):
        """
        Revokes the role a pending invitation grants on its scope. Look into
        `RoleAssignmentHandler.delete_scoped_invitation` for further details.
        """

        workspace = scoped_invitation.invitation.workspace
        params = cls.Params(
            scoped_invitation.id,
            scoped_invitation.invitation_id,
            scoped_invitation.invitation.email,
            scoped_invitation.role.uid,
            _scope_type_name(scoped_invitation),
            scoped_invitation.scope_id,
            workspace.id,
            workspace.name,
        )
        RoleAssignmentHandler().delete_scoped_invitation(user, scoped_invitation)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(),
            workspace=workspace,
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


def _scope_type_name(scoped_invitation: WorkspaceScopedInvitation) -> str:
    """
    The object scope type name of the scope an invitation grants a role on, read
    from the content type so that it is known even when the scope is gone.
    """

    return object_scope_type_registry.get_by_model(
        scoped_invitation.scope_type.model_class()
    ).type
