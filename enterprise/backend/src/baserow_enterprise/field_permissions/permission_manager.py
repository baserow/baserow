from collections import defaultdict
from functools import partial
from typing import Callable, Dict, List, Literal, Optional, TypedDict

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db.models import Exists, OuterRef, Q, QuerySet

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import (
    SubmitAnonymousFieldValuesOperationType,
    WriteFieldValuesOperationType,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.agents.subjects import AgentSubjectType
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
    FIELD_PERMISSION_EDITOR_ROLE_UID,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment
from baserow_enterprise.teams.models import Team, TeamSubject
from baserow_premium.license.handler import LicenseHandler

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
        AgentSubjectType.type,
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

    def _get_custom_field_ids_by_actor(
        self,
        workspace: Workspace,
        actors: List[Actor],
        field_ids: set[int],
    ) -> Dict[Actor, set[int]]:
        """
        Returns the custom fields selected for each actor, either directly or via a
        team. The membership and assignments are fetched in batches to avoid queries
        per permission check.

        :param workspace: The workspace containing the field permission assignments.
        :param actors: The actors whose selected custom fields should be returned.
        :param field_ids: The custom field IDs relevant to the permission checks.
        :return: The selected custom field IDs for each actor. Actors without a
            matching assignment resolve to an empty set.
        """

        user_model = subject_type_registry.get(UserSubjectType.type).model_class
        actors_by_id = {
            actor.id: actor for actor in actors if isinstance(actor, user_model)
        }
        result = defaultdict(set)
        if not actors_by_id or not field_ids:
            return result

        content_types = ContentType.objects.get_for_models(user_model, Team, Field)
        user_content_type = content_types[user_model]
        team_content_type = content_types[Team]
        field_content_type = content_types[Field]

        actor_ids_by_team_id = defaultdict(set)
        for team_id, actor_id in TeamSubject.objects.filter(
            team__workspace=workspace,
            team__trashed=False,
            subject_type=user_content_type,
            subject_id__in=actors_by_id,
        ).values_list("team_id", "subject_id"):
            actor_ids_by_team_id[team_id].add(actor_id)

        assignments = RoleAssignment.objects.filter(
            workspace=workspace,
            scope_type=field_content_type,
            scope_id__in=field_ids,
            role__uid=FIELD_PERMISSION_EDITOR_ROLE_UID,
        ).filter(
            Q(subject_type=user_content_type, subject_id__in=actors_by_id)
            | Q(
                subject_type=team_content_type,
                subject_id__in=actor_ids_by_team_id,
            )
        )

        for subject_type_id, subject_id, field_id in assignments.values_list(
            "subject_type_id", "subject_id", "scope_id"
        ):
            if subject_type_id == user_content_type.id:
                result[actors_by_id[subject_id]].add(field_id)
            else:
                for actor_id in actor_ids_by_team_id[subject_id]:
                    result[actors_by_id[actor_id]].add(field_id)

        return result

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

        # Some checks can be resolved immediately, while role-based and custom checks
        # also need the actor's effective role on the table.
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
                if not isinstance(
                    check.actor,
                    subject_type_registry.get(UserSubjectType.type).model_class,
                ):
                    result[check] = PermissionDenied()
                    continue
            else:
                # Check actor role and permissions later.
                pass
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

        custom_field_ids = {
            check.context.id
            for check in remaining_role_checks
            if field_permissions_map[check.context.id].role
            == FieldPermissionsRoleEnum.CUSTOM.value
        }
        custom_field_ids_by_actor = self._get_custom_field_ids_by_actor(
            workspace,
            list(checks_by_actor_and_context),
            custom_field_ids,
        )

        scope_includes_cache = {}
        for actor, table_checks in checks_by_actor_and_context.items():
            for table, checks in table_checks.items():
                computed_roles = role_handler.get_computed_roles(
                    roles_per_scope_by_actor[actor], table, scope_includes_cache
                )
                checks_results = self._get_checks_results(
                    checks,
                    computed_roles,
                    field_permissions_map,
                    custom_field_ids_by_actor[actor],
                )
                result.update(checks_results)

        return result

    def _is_custom_permission_allowed(
        self,
        field_id: int,
        custom_field_ids: set[int],
        get_computed_roles: Callable[[], List[Role]],
    ) -> bool:
        """Returns whether a CUSTOM permission allows writing to a field.

        The actor must be selected directly or through a team and must also have an
        effective Editor-or-higher role on the field's table. The role getter is only
        evaluated for selected actors.

        :param field_id: The ID of the field being checked.
        :param custom_field_ids: The IDs of fields for which the actor is selected.
        :param get_computed_roles: Returns the actor's effective roles on the table.
        :return: Whether the actor can write to the custom-permission field.
        """

        return field_id in custom_field_ids and self._is_operation_allowed(
            get_computed_roles(), FieldPermissionsRoleEnum.EDITOR.value
        )

    def _get_checks_results(
        self,
        checks: List[PermissionCheck],
        computed_roles: List[Role],
        field_permissions_map: Dict[int, FieldPermissions],
        custom_field_ids: set[int],
    ) -> Dict[PermissionCheck, bool | PermissionDenied]:
        """
        Returns permission results for field checks sharing an actor and table.

        Each field can require a different role. CUSTOM permissions additionally use
        ``custom_field_ids`` to determine whether the actor was explicitly selected.

        :param checks: The list of checks to perform.
        :param computed_roles: The list of computed roles for the actor.
        :param field_permissions_map: The field permissions keyed by field ID.
        :param custom_field_ids: The IDs of custom fields selected for the actor.
        :return: A dictionary with the check as the key and True or PermissionDenied
            as the value.
        """

        result = {}
        for check in checks:
            field_id = check.context.id
            required_role = field_permissions_map[field_id].role
            if required_role == FieldPermissionsRoleEnum.CUSTOM.value:
                is_allowed = self._is_custom_permission_allowed(
                    field_id,
                    custom_field_ids,
                    lambda: computed_roles,
                )
            else:
                is_allowed = self._is_operation_allowed(computed_roles, required_role)

            if is_allowed:
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
        actor, verifies that the actor has permission to perform the operation.

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
            return dict.fromkeys(field_checks, True)

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

        role_handler = RoleAssignmentHandler()
        roles_by_scope = role_handler.get_roles_per_scope(workspace, actor)
        custom_field_ids = {
            field_perm.field_id
            for field_perm in field_perms
            if field_perm.role == FieldPermissionsRoleEnum.CUSTOM.value
        }
        selected_custom_field_ids = self._get_custom_field_ids_by_actor(
            workspace, [actor], custom_field_ids
        )[actor]

        can_write_values_exceptions = set()
        can_submit_values_exceptions = set()
        computed_roles_by_table_id = {}
        scope_includes_cache = {}

        def get_computed_roles_for_table(table):
            """Return and memoize the actor's effective roles for a table.

            :param table: The table whose effective roles should be returned.
            :return: The actor's effective roles for the table.
            """

            if table.id not in computed_roles_by_table_id:
                computed_roles_by_table_id[table.id] = role_handler.get_computed_roles(
                    roles_by_scope, table, scope_includes_cache
                )
            return computed_roles_by_table_id[table.id]

        # Verify if the actor has the required permissions for each field permission.
        # If not, add the field id to the exceptions list.
        for field_perm in field_perms:
            if not field_perm.allow_in_forms:
                can_submit_values_exceptions.add(field_perm.field_id)

            if field_perm.role == FieldPermissionsRoleEnum.NOBODY.value:
                can_write_values_exceptions.add(field_perm.field_id)
            elif field_perm.role == FieldPermissionsRoleEnum.CUSTOM.value:
                can_edit = self._is_custom_permission_allowed(
                    field_perm.field_id,
                    selected_custom_field_ids,
                    partial(
                        get_computed_roles_for_table,
                        field_perm.field.table,
                    ),
                )
                if not can_edit:
                    can_write_values_exceptions.add(field_perm.field_id)
            else:
                can_edit = self._is_operation_allowed(
                    get_computed_roles_for_table(field_perm.field.table),
                    field_perm.role,
                )
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
