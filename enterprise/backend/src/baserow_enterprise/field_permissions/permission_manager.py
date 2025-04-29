from collections import defaultdict
from functools import partial
from typing import Dict, List, Literal, Optional, TypedDict

from django.contrib.auth.models import AbstractUser
from django.db.models import Exists, OuterRef, QuerySet

from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import (
    SubmitAnonymousFieldValuesOperationType,
    WriteFieldValuesOperationType,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import Workspace
from baserow.core.registries import PermissionManagerType, subject_type_registry
from baserow.core.subjects import AnonymousUserSubjectType, UserSubjectType
from baserow.core.types import Actor, PermissionCheck
from baserow_enterprise.features import RBAC
from baserow_enterprise.role.constants import (
    ADMIN_ROLE_UID,
    BUILDER_ROLE_UID,
    EDITOR_ROLE_UID,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

from .models import FieldPermissions, FieldPermissionsRoleEnum

ALLOWED_ROLES_MAP = {
    FieldPermissionsRoleEnum.ADMIN.value: {ADMIN_ROLE_UID},
    FieldPermissionsRoleEnum.BUILDER.value: {BUILDER_ROLE_UID, ADMIN_ROLE_UID},
    FieldPermissionsRoleEnum.EDITOR.value: {
        EDITOR_ROLE_UID,
        BUILDER_ROLE_UID,
        ADMIN_ROLE_UID,
    },
}


class OperationPermissionContent(TypedDict):
    default: bool
    exceptions: List[int]


class FieldPermissionManagerType(PermissionManagerType):
    type = "write_field_values"
    supported_actor_types = [
        UserSubjectType.type,
        AnonymousUserSubjectType.type,
    ]

    def is_enabled(self, workspace: Workspace):
        """
        Checks whether this permission manager should be enabled or not for a
        particular workspace.

        :param workspace: The workspace in which we want to use this permission manager.
        """

        return local_cache.get(
            f"has_rbac_permission_{workspace.id}",
            partial(LicenseHandler.workspace_has_feature, RBAC, workspace),
        )

    def _filter_pertinent_checks(
        self, checks: List[PermissionCheck]
    ) -> List[PermissionCheck]:
        """
        Filters out the checks that are not relevant for this permission manager.
        """

        ops_allowed = {
            WriteFieldValuesOperationType.type,
            SubmitAnonymousFieldValuesOperationType.type,
        }

        return [c for c in checks if c.operation_name in ops_allowed]

    def check_field_permissions(
        self, checks: List[PermissionCheck], workspace=None, include_trash=False
    ):
        # Fetch all field permissions for the fields in the checks.
        field_permissions_map = {
            field_perm.field_id: field_perm
            for field_perm in FieldPermissions.objects.filter(
                field__in=(c.context for c in checks)
            )
        }
        result = {}

        # Some checks can be resolved immediately like NOBODY or CUSTOM roles.
        # Otherwise, we need to check the actor's roles and permissions later.
        remaining_role_checks = []
        for check in checks:
            field = check.context
            field_perm = field_permissions_map.get(field.id)
            if field_perm is None:  # No restriction
                result[check] = True
                continue

            op_name = check.operation_name
            if op_name == SubmitAnonymousFieldValuesOperationType.type:
                result[check] = (
                    True if field_perm.allow_in_forms else PermissionDenied()
                )
                continue

            # WriteFieldValuesOperationType
            required_role = field_perm.role
            if required_role == FieldPermissionsRoleEnum.NOBODY.value:
                result[check] = PermissionDenied()
                continue
            elif required_role == FieldPermissionsRoleEnum.CUSTOM.value:
                continue  # TODO: implement the check here for CUSTOM_ROLE_UID
            else:
                # check actor role and permissions later

                remaining_role_checks.append(check)
        if not remaining_role_checks:  # All checks resolved
            return result

        # Compute roles per scope for each actor and verify permissions.
        actors_by_subject_type = defaultdict(set)
        checks_by_actor_and_context = defaultdict(lambda: defaultdict(list))
        for check in remaining_role_checks:
            actor, _, field = check
            s_type = subject_type_registry.get_by_model(actor)
            actors_by_subject_type[s_type].add(actor)
            checks_by_actor_and_context[actor][field.table].append(check)

        role_handler = RoleAssignmentHandler()
        roles_per_scope_by_actor = {}
        for actor_subject_type, actors in actors_by_subject_type.items():
            roles_per_scope_by_actor.update(
                role_handler.get_roles_per_scope_for_actors(
                    workspace, actor_subject_type, actors, include_trash=include_trash
                )
            )

        scope_includes_cache = {}
        for actor, table_checks in checks_by_actor_and_context.items():
            for table, checks in table_checks.items():
                computed_roles = role_handler.get_computed_roles(
                    roles_per_scope_by_actor[actor], table, scope_includes_cache
                )
                checks_results = self._get_checks_results(
                    checks, computed_roles, field_permissions_map
                )
                result.update(checks_results)

        return result

    def _get_checks_results(
        self,
        checks: List[PermissionCheck],
        computed_roles: List[Role],
        field_permissions_map: Dict[int, FieldPermissions],
    ) -> Dict[PermissionCheck, bool | PermissionDenied]:
        """
        Helper function to get the results of all the checks for a given actor defined
        by the list of computed roles and a required role common to all the checks.
        This function will return a dictionary with the check as the key and True or
        PermissionDenied as the value.

        :param checks: The list of checks to perform.
        :param computed_roles: The list of computed roles for the actor.
        :param required_role: The required role for the checks.
        :return: A dictionary with the check as the key and True or PermissionDenied
            as the value.
        """

        result = {}
        for check in checks:
            field_id = check.context.id
            required_role = field_permissions_map[field_id].role
            if self._is_operation_allowed(computed_roles, required_role):
                result[check] = True
            else:
                result[check] = PermissionDenied()
        return result

    def _is_operation_allowed(
        self,
        computed_roles: List[Role],
        required_role: Literal["ADMIN", "BUILDER", "EDITOR"],
    ) -> bool:
        """
        Given a required role for the operation and a list of computed roles for an
        actor, verify the actor have the required permissions to perform the operation.

        :param computed_roles: The list of computed RBAC roles for the actor.
        :param required_role: The required role for the operation.
        :return: True if the actor has the required permissions, False otherwise.
        """

        valid_roles = ALLOWED_ROLES_MAP[required_role]
        return bool({r.uid for r in computed_roles} & valid_roles)

    def check_multiple_permissions(
        self,
        checks: List[PermissionCheck],
        workspace: Workspace | None = None,
        include_trash: Optional[bool] = False,
    ) -> Dict[PermissionCheck, bool | PermissionDenied]:
        """
        Filters out the checks that are not relevant for this permission manager and
        checks the permissions for the remaining checks. This function will return a
        dictionary with the check as the key and True or PermissionDenied as the value.

        :param checks: The list of checks to perform.
        :param workspace: The workspace in which we want to use this permission manager.
        :param include_trash: Whether to include trashed objects in the checks.
        :return: A dictionary with the check as the key and True or PermissionDenied
            as the value.
        """

        # Exclude checks that are not relevant for this permission manager.
        field_checks = self._filter_pertinent_checks(checks)
        if not field_checks:
            return {}

        if workspace is None or not self.is_enabled(workspace):
            # Permissions granted if RBAC is not enabled.
            return {check: True for check in field_checks}

        return self.check_field_permissions(
            field_checks, workspace, include_trash=include_trash
        )

    def get_permissions_object(
        self,
        actor: AbstractUser,
        workspace: Workspace | None = None,
        for_operation_types=None,
        use_object_scope=False,
    ) -> List[Dict[str, OperationPermissionContent]]:
        """
        Returns the permission object for this permission manager. The permission object
        looks like this:
        ```
        {
            "database.table.field.write_values": {
                default=True,
                exceptions=[1, 2, 3],
            },
            "database.table.field.submit_anonymous_values": {
                default=True,
                exceptions=[4, 5, 6],
            },
        }
        ```
        """

        if workspace is None or not self.is_enabled(workspace):
            return None

        # Get relevant FieldPermissions excluding trashed fields and tables where the
        # user does not have access to.
        table_qs = TableHandler().list_workspace_tables(actor, workspace)
        field_perms = FieldPermissions.objects.filter(
            field__trashed=False,
            field__table__in=table_qs,
        ).select_related("field__table__database__workspace")

        roles_by_scope = RoleAssignmentHandler().get_roles_per_scope(workspace, actor)

        can_write_values_exceptions = set()
        can_submit_values_exceptions = set()

        # Verify if the actor has the required permissions for each field permission.
        # If not, add the field id to the exceptions list.
        for field_perm in field_perms:
            if not field_perm.allow_in_forms:
                can_submit_values_exceptions.add(field_perm.field_id)

            if field_perm.role == FieldPermissionsRoleEnum.NOBODY.value:
                can_write_values_exceptions.add(field_perm.field_id)
            elif field_perm.role == FieldPermissionsRoleEnum.CUSTOM.value:
                # TODO: implement the check here.
                continue
            else:
                computed_roles = RoleAssignmentHandler().get_computed_roles(
                    roles_by_scope, field_perm.field.table
                )
                can_edit = self._is_operation_allowed(computed_roles, field_perm.role)
                if not can_edit:
                    can_write_values_exceptions.add(field_perm.field_id)

        return {
            WriteFieldValuesOperationType.type: OperationPermissionContent(
                default=True, exceptions=list(can_write_values_exceptions)
            ),
            SubmitAnonymousFieldValuesOperationType.type: OperationPermissionContent(
                default=True, exceptions=list(can_submit_values_exceptions)
            ),
        }

    def filter_queryset(
        self,
        actor: Actor,
        operation_name: str,
        queryset: QuerySet[Field],
        workspace: Optional[Workspace] = None,
    ) -> QuerySet:
        # Only needed to filter fields that can be used in forms for now.
        if operation_name != SubmitAnonymousFieldValuesOperationType.type:
            return queryset

        if workspace is None or not self.is_enabled(workspace):
            return queryset

        return (
            queryset.filter(
                ~Exists(
                    FieldPermissions.objects.filter(
                        field_id=OuterRef("id"), allow_in_forms=False
                    ).values("field_id")[:1]
                )
            ),
            True,
        )
