from collections import defaultdict
from functools import partial
from typing import Dict, List, TypedDict
from django.contrib.auth.models import AbstractUser
from baserow.contrib.database.fields.operations import WriteFieldDataOperationType
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import User, Workspace
from baserow.core.registries import PermissionManagerType
from baserow.core.subjects import UserSubjectType
from baserow.core.cache import local_cache
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import RBAC
from baserow_enterprise.role.constants import (
    ADMIN_ROLE_UID,
    BUILDER_ROLE_UID,
    EDITOR_ROLE_UID,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_premium.license.handler import LicenseHandler
from baserow.core.registries import (
    PermissionManagerType,
    subject_type_registry,
)
from .models import FieldPermission


class OperationPermissionContent(TypedDict):
    default: bool
    exceptions: List[int]


class FieldPermissionManagerType(PermissionManagerType):
    type = "field"
    supported_actor_types = [UserSubjectType.type]

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

    def check_multiple_permissions(
        self, checks: List[PermissionCheck], workspace=None, include_trash=False
    ):
        """
        Checks the permissions for each check.
        """

        # Verify if there are any permission to check for this permission manager
        field_checks = tuple(
            filter(
                lambda c: c.operation_name == WriteFieldDataOperationType.type, checks
            )
        )
        if not field_checks:
            return {}

        if workspace is None or not self.is_enabled(workspace):
            # Permissions granted if RBAC is not enabled.
            return {check: True for check in field_checks}

        required_roles = {
            fp.field_id: fp.role
            for fp in FieldPermission.objects.filter(
                field__in=(c.context for c in field_checks)
            )
        }
        result = {}

        pending_checks = []
        for check in field_checks:
            field = check.context
            required_role = required_roles.get(field.id)
            if required_role is None:  # No restriction
                result[check] = True
            elif required_role == FieldPermission.NOBDOY_ROLE_UID:
                result[check] = PermissionDenied()
            elif required_role == FieldPermission.CUSTOM_ROLE_UID:
                # TODO: implement the check here.
                continue
            else:
                # We need to check the role for this actor
                pending_checks.append(check)

        if not pending_checks:
            return result

        # Workspace actor by subject_type
        actors_by_subject_type = defaultdict(set)
        for actor, _, _ in pending_checks:
            s_type = subject_type_registry.get_by_model(actor)
            actors_by_subject_type[s_type].add(actor)

        role_handler = RoleAssignmentHandler()
        scope_includes_cache = {}
        for actor_subject_type, actors in actors_by_subject_type.items():
            computed_role_cache = {}
            roles_per_scope_by_actor = role_handler.get_roles_per_scope_for_actors(
                workspace, actor_subject_type, actors, include_trash=include_trash
            )

            for check in field_checks:
                actor, _, field = check

                table = field.table
                cache_key = (actor.id, f"{type(table).__name__}__{table.id}")
                if cache_key not in computed_role_cache:
                    # Compute the actual role for this check
                    computed_role_cache[cache_key] = role_handler.get_computed_roles(
                        roles_per_scope_by_actor[actor],
                        table,
                        scope_includes_cache,
                    )

                computed_roles = computed_role_cache[cache_key]
                if self.is_operation_allowed(computed_roles, required_roles[field.id]):
                    result[check] = True
                else:
                    result[check] = PermissionDenied()

        return result

    def is_operation_allowed(self, computed_roles, required_role) -> bool:
        valid_roles = {ADMIN_ROLE_UID}
        if required_role == BUILDER_ROLE_UID:
            valid_roles |= {BUILDER_ROLE_UID}

        return bool({r.uid for r in computed_roles} & valid_roles)

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
        TBD
        ```
        """

        return {}
