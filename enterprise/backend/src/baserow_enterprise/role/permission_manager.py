from collections import defaultdict
from functools import cached_property, partial
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from baserow_premium.license.handler import LicenseHandler

from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import Workspace
from baserow.core.registries import (
    OperationType,
    PermissionManagerType,
    object_scope_type_registry,
    operation_type_registry,
    subject_type_registry,
)
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import RBAC
from baserow_enterprise.role.handler import RoleAssignmentHandler

from .constants import READ_ONLY_ROLE_UID
from .models import Role

User = get_user_model()


class OperationPermissionContent(TypedDict):
    default: bool
    exceptions: List[int]


class RolePermissionManagerType(PermissionManagerType):
    type = "role"
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

    def get_role_operations(self, role: Role) -> List[str]:
        """
        Return the operation name list for the role with the given role_id.

        :param role: The role we want the operation names for.
        :return: A list of role operation name.
        """

        return set([op.name for op in role.operations.all()])

    @cached_property
    def read_operations(self) -> Set[str]:
        """
        Return the read operation list.
        """

        return set(
            op.name
            for op in RoleAssignmentHandler()
            .get_role_by_uid(READ_ONLY_ROLE_UID)
            .operations.all()
        )

    def check_multiple_permissions(
        self, checks: List[PermissionCheck], workspace=None, include_trash=False
    ):
        """
        Checks the permissions for each check.
        """

        if workspace is None or not self.is_enabled(workspace):
            return {}

        # Workspace actor by subject_type
        actors_by_subject_type = defaultdict(set)
        checks_by_actor_and_context = defaultdict(lambda: defaultdict(list))
        for check in checks:
            actor, _, context = check
            s_type = subject_type_registry.get_by_model(actor)
            actors_by_subject_type[s_type].add(actor)
            checks_by_actor_and_context[actor][context].append(check)

        result = {}
        roles_per_scope_by_actor = {}
        for actor_subject_type, actors in actors_by_subject_type.items():
            roles_per_scope_by_actor.update(
                RoleAssignmentHandler().get_roles_per_scope_for_actors(
                    workspace, actor_subject_type, actors, include_trash=include_trash
                )
            )

        scope_includes_cache = {}
        for actor, context_and_checks in checks_by_actor_and_context.items():
            for context, checks in context_and_checks.items():
                computed_roles = RoleAssignmentHandler().get_computed_roles(
                    roles_per_scope_by_actor[actor], context, scope_includes_cache
                )
                permitted_operations = set(
                    [
                        operation_name
                        for r in computed_roles
                        for operation_name in self.get_role_operations(r)
                    ]
                )
                check_results = {
                    check: (
                        True
                        if check.operation_name in permitted_operations
                        else PermissionDenied()
                    )
                    for check in checks
                }
                result.update(check_results)

        return result

    def get_operation_policy(
        self,
        roles_by_scope: List[Tuple[Any, List[Role]]],
        operation_type: OperationType,
        use_object_scope: bool = False,
    ) -> Tuple[bool, Set[Any]]:
        """
        Compute the default policy and exceptions for an operation given the
        role assignments.

        :param role_assignments: The role assignments used to compute the policy.
        :param operation_type: The operation type we want the policy for.
        :param use_object_scope: Use the `object_scope` instead of the `context_scope`
            of the scope_type. This change the type of returned objects.
        :return: A tuple. The first element is the default policy. The second element
            is a set of context or object that are exceptions to the default policy.
        """

        base_scope_type = (
            operation_type.object_scope
            if use_object_scope
            else operation_type.context_scope
        )

        # Default permissions at the workspace level
        _, default_workspace_roles = roles_by_scope[0]
        default = any(
            [
                operation_type.type in self.get_role_operations(r)
                for r in default_workspace_roles
            ]
        )
        exceptions = set()
        inclusions = set()

        for scope, roles in roles_by_scope[1:]:
            allowed_operations = set()

            for role in roles:
                allowed_operations.update(self.get_role_operations(role))

            scope_type = object_scope_type_registry.get_by_model(scope)

            # First case
            # The scope of the role assignment includes the scope of the operation
            # So it has an influence on the result
            if object_scope_type_registry.scope_type_includes_scope_type(
                scope_type, base_scope_type
            ):
                context_exception = scope
                # Remove or add exceptions to the exception list according to the
                # default policy for the workspace
                if operation_type.type not in allowed_operations:
                    if default:
                        exceptions.add(context_exception)
                        inclusions.discard(context_exception)
                    else:
                        inclusions.add(context_exception)
                        exceptions.discard(context_exception)
                else:
                    if default:
                        inclusions.add(context_exception)
                        exceptions.discard(context_exception)
                    else:
                        exceptions.add(context_exception)
                        inclusions.discard(context_exception)

            # Second case
            # The scope of the role assignment is included by the role of the operation
            # And we are doing a read operation
            # So we must enable the read operation for the parent
            elif (
                operation_type.type in self.read_operations
                and allowed_operations
                and object_scope_type_registry.scope_type_includes_scope_type(
                    base_scope_type, scope_type
                )
            ):
                # - It's a read operation and
                # - we have a children that have at least one allowed operation
                # -> we should then allow all read operations for any ancestor of
                # this scope object.
                found_object = object_scope_type_registry.get_parent(
                    scope, at_scope_type=base_scope_type
                )

                if default:
                    exceptions.discard(found_object)
                    inclusions.add(found_object)
                else:
                    exceptions.add(found_object)
                    inclusions.discard(found_object)

        return default, exceptions, inclusions

    def get_permissions_object(
        self,
        actor: AbstractUser,
        workspace: Optional[Workspace] = None,
        for_operation_types=None,
        use_object_scope=False,
    ) -> List[Dict[str, OperationPermissionContent]]:
        """
        Returns the permission object for this permission manager. The permission object
        looks like this:
        ```
        {
            "operation_name1": {"default": True, "exceptions": [3, 5]},
            "operation_name2": {"default": False, "exceptions": [12, 18]},
            ...
        }
        ```
        where `permission_name1` is the name of an operation and for each operation, if
        the operation is permitted by default or not and `exceptions` contains the list
        of context IDs that are an exception to the default rule.
        """

        if workspace is None or not self.is_enabled(workspace):
            return None

        # Get all role assignments for this actor into this workspace
        roles_by_scope = RoleAssignmentHandler().get_roles_per_scope(workspace, actor)

        policy_per_operation = defaultdict(lambda: {"default": False, "exceptions": []})

        scope_map_with_mixed_types_per_scope = defaultdict(set)

        all_operations = for_operation_types or operation_type_registry.get_all()

        # First, for each operation we want the default policy and exceptions
        for operation_type in all_operations:
            default, exceptions, inclusions = self.get_operation_policy(
                roles_by_scope, operation_type, use_object_scope
            )

            base_scope_type = (
                operation_type.object_scope
                if use_object_scope
                else operation_type.context_scope
            )

            policy_per_operation[operation_type.type]["default"] = default
            policy_per_operation[operation_type.type]["exceptions"] = exceptions
            policy_per_operation[operation_type.type]["inclusions"] = inclusions

            # We store the exceptions/inclusions by scope to get all
            # objects at once later
            scope_map_with_mixed_types_per_scope[base_scope_type] |= (
                exceptions | inclusions
            )

        # Get all objects for all exceptions/inclusions at once to improve perfs
        exception_ids_per_scope = {}
        for object_scope, exceptions in scope_map_with_mixed_types_per_scope.items():
            exception_ids_per_scope[object_scope] = {
                scope: {o.id for o in exc}
                for scope, exc in object_scope.get_objects_in_scopes(exceptions).items()
            }

        # Dispatch actual context object ids for each exceptions/inclusions scopes
        policy_per_operation_with_exception_ids = {}
        for operation_type in all_operations:
            inclusions = policy_per_operation[operation_type.type]["inclusions"]
            exclusions = policy_per_operation[operation_type.type]["exceptions"]
            ordered_scope = sorted(
                inclusions | exclusions,
                key=lambda s: object_scope_type_registry.get_by_model(s).level,
            )

            base_scope_type = (
                operation_type.object_scope
                if use_object_scope
                else operation_type.context_scope
            )

            # Gather all ids for all scopes of the exception list of this operation
            exceptions_ids = set()
            for scope in ordered_scope:
                if scope in exclusions:
                    exceptions_ids |= exception_ids_per_scope[base_scope_type][scope]
                if scope in inclusions:
                    exceptions_ids -= exception_ids_per_scope[base_scope_type][scope]

            policy_per_operation_with_exception_ids[operation_type.type] = {
                "default": policy_per_operation[operation_type.type]["default"],
                "exceptions": list(exceptions_ids),
            }

        return policy_per_operation_with_exception_ids

    def filter_queryset(self, actor, operation_name, queryset, workspace=None):
        """
        Filter the given queryset according to the role given for the specified
        operation.
        """

        if workspace is None or not self.is_enabled(workspace):
            return

        operation_type = operation_type_registry.get(operation_name)

        permission_obj = self.get_permissions_object(
            actor,
            workspace,
            for_operation_types=[operation_type],
            use_object_scope=True,
        )

        default = permission_obj[operation_type.type]["default"]
        exceptions = permission_obj[operation_type.type]["exceptions"]

        # Finally filter the queryset with the exception filter.
        if default:
            if exceptions:
                queryset = queryset.exclude(id__in=exceptions)
        else:
            if exceptions:
                queryset = queryset.filter(id__in=exceptions)
            else:
                queryset = queryset.none()

        return queryset
