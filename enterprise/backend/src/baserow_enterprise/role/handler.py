from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from baserow_premium.license.handler import LicenseHandler

from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.mixins import TrashableModelMixin
from baserow.core.models import Workspace, WorkspaceUser
from baserow.core.object_scopes import CoreObjectScopeType
from baserow.core.registries import (
    SubjectType,
    object_scope_type_registry,
    subject_type_registry,
)
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck, ScopeObject, Subject
from baserow_enterprise.exceptions import (
    ScopeNotExist,
    SubjectNotExist,
    SubjectUnsupported,
)
from baserow_enterprise.features import RBAC
from baserow_enterprise.models import RoleAssignment
from baserow_enterprise.role.models import Role
from baserow_enterprise.signals import (
    role_assignment_created,
    role_assignment_deleted,
    role_assignment_updated,
)
from baserow_enterprise.teams.models import Team, TeamSubject

from .constants import (
    ALLOWED_SUBJECT_TYPE_BY_PRIORITY,
    NO_ACCESS_ROLE_UID,
    NO_ROLE_LOW_PRIORITY_ROLE_UID,
    READ_ONLY_ROLE_UID,
    ROLE_ASSIGNABLE_OBJECT_MAP,
)
from .types import NewRoleAssignment

User = get_user_model()
ROLE_ASSIGNMENT_CACHE_KEY_PREFIX = "role_assignments"


def _clear_role_assignments_from_local_cache():
    """
    Simple helper to clear the local cache for role assignments when needed.
    """

    local_cache.delete(f"{ROLE_ASSIGNMENT_CACHE_KEY_PREFIX}_*")


def clear_roles_from_local_cache():
    """
    Decorator to use for methods that need to clear the role assignment cache at the end
    of their implementation.
    """

    def decorator(method):
        def wrapper(*args, **kwargs):
            try:
                result = method(*args, **kwargs)
            finally:
                _clear_role_assignments_from_local_cache()
            return result

        return wrapper

    return decorator


class RoleAssignmentHandler:
    def _get_role_assignments_for_valid_subjects_qs(self) -> QuerySet:
        """
        Constructs base queryset for role_assignments in order to filter out any
        role assignment related to a trashed subject.
        """

        id_filters = Q()
        for subject_type in subject_type_registry.get_all():
            if issubclass(subject_type.model_class, TrashableModelMixin):
                id_filters.add(
                    ~Q(
                        subject_id__in=subject_type.model_class.trash.all().values_list(
                            "id", flat=True
                        ),
                        subject_type=subject_type.get_content_type(),
                    ),
                    Q.AND,
                )

        return RoleAssignment.objects.filter(id_filters)

    @classmethod
    def _get_role_caches(cls):
        if not getattr(cls, "_init", False):
            role_by_uid = {}
            role_by_id = {}
            for role in Role.objects.prefetch_related("operations").all():
                role_by_uid[role.uid] = role
                role_by_id[role.id] = role
            cls._role_cache_by_uid, cls._role_cache_by_id = role_by_uid, role_by_id
            cls._init = True

        return cls._role_cache_by_uid, cls._role_cache_by_id

    def get_role_by_uid(self, role_uid: str, use_fallback=False) -> Role:
        """
        Returns the role for the given uid.
        If `role_uid` isn't found, we fall back to `role_fallback`.

        :param role_uid: The uid we want the role for.
        :param use_fallback: If true and the role_uid is not found, we fallback to
           the NO_ACCESS role.
        :return: A role.
        """

        # Translate MEMBER to builder for compatibility with basic "role" name.
        if role_uid == "MEMBER":
            role_uid = "BUILDER"

        try:
            if role_uid not in self._get_role_caches()[0]:
                raise Role.DoesNotExist()

            return self._get_role_caches()[0][role_uid]
        except Role.DoesNotExist:
            if use_fallback:
                return self.get_role_by_uid(NO_ACCESS_ROLE_UID)
            else:
                raise

    def get_role_by_id(self, role_id: int) -> Role:
        """
        Returns the role for the given id.

        :param role_id: The id we want the role for.
        :return: A role.
        """

        if role_id not in self._get_role_caches()[1]:
            raise Role.DoesNotExist()

        return self._get_role_caches()[1][role_id]

    def get_current_role_assignment(
        self,
        subject: Union[AbstractUser, Team],
        workspace: Workspace,
        scope: Optional[ScopeObject] = None,
    ) -> Union[RoleAssignment, None]:
        """
        Returns the current assigned role for the given Workspace/Subject/Scope.

        :param subject: The subject we want the role for.
        :param workspace: The workspace in which you want the user or team role.
        :param scope: An optional scope on which the role applies.
        :return: The current `RoleAssignment` or `None` if no role is defined for the
            given parameters.
        """

        if scope is None:
            scope = workspace

        key = (subject, scope)

        return self.get_current_role_assignments(workspace, [key])[key]

    def get_current_role_assignments(
        self,
        workspace: Workspace,
        for_subject_scope: List[Tuple[Subject, ScopeObject]],
        include_trash=False,
    ) -> Dict[Tuple[Subject, ScopeObject], Optional[RoleAssignment]]:
        """
        Returns the current assigned role for the given Subject/Scope tuples.

        :param workspace: The workspace in which you want the role assignments.
        :param for_subject_scope: A list of (subject, scope) with want the role for.
        :return: The current `RoleAssignment` or `None` if no role is defined for the
            scope each of the given tuples.
        """

        user_subject_type = subject_type_registry.get(UserSubjectType.type)

        # Workspace all scopes and subjects to get their content_type
        scope_types = set([Workspace])
        subject_types = set()
        for subject, scope in for_subject_scope:
            scope_types.add(type(scope))
            subject_types.add(type(subject))

        content_types = ContentType.objects.get_for_models(
            *subject_types,
            *scope_types,
        )

        # Generate the query to get all the current role assignments for the given
        # tuples
        # Exception for user subject for workspace scope as we read the permission
        # from the workspace_users object
        subject_scope_q = Q()
        user_subject_with_workspace_scope_by_id = dict()
        for subject, scope in for_subject_scope:
            if (
                isinstance(subject, user_subject_type.model_class)
                and scope == workspace
            ):
                # Exception for users with workspace scope
                user_subject_with_workspace_scope_by_id[subject.id] = subject
            else:
                subject_scope_q |= Q(
                    subject_type=content_types[type(subject)],
                    subject_id=subject.id,
                    scope_id=scope.id,
                    scope_type=content_types[type(scope)],
                )

        role_assignments = (
            self._get_role_assignments_for_valid_subjects_qs()
            .prefetch_related("role")
            .filter(workspace=workspace)
            .filter(subject_scope_q)
        )

        # Create a map to easily match the given tuples at the end
        # without triggering the django query for the related content
        role_assignments_by_user_id_scope_id = {
            (ra.subject_type, ra.subject_id, ra.scope_type, ra.scope_id): ra
            for ra in role_assignments
        }

        # If we are get the role of a user at a workspace scope level,
        # we get it from the role uid in the `.permissions` property of the
        # `WorkspaceUser` object instead to remain compatible with other permission
        # managers. This makes it easy to switch from one permission manager to
        # another without losing nor duplicating information
        if user_subject_with_workspace_scope_by_id:
            for user_id, permissions in (
                CoreHandler()
                .get_workspace_users(
                    workspace,
                    user_subject_with_workspace_scope_by_id.values(),
                    include_trash=include_trash,
                )
                .values_list("user_id", "permissions")
            ):
                role = self.get_role_by_uid(permissions, use_fallback=True)
                key = (
                    user_subject_type.get_content_type(),
                    user_id,
                    content_types[Workspace],
                    workspace.id,
                )
                subject = user_subject_with_workspace_scope_by_id[user_id]
                # We need to fake a RoleAssignment instance here to keep the same
                # return interface
                fake_role_assignment = RoleAssignment(
                    subject=subject,
                    subject_id=subject.id,
                    subject_type=content_types[type(subject)],
                    role=role,
                    workspace=workspace,
                    scope=workspace,
                    scope_type=content_types[Workspace],
                )
                role_assignments_by_user_id_scope_id[key] = fake_role_assignment

        # Dispatch each role assignments to the (subject, scope) tuple it belongs to
        # if there is one for this tuple otherwise None which means no previous
        # role existed for the (subject, scope) tuple.
        roles_by_user_scope = {}
        for subject, scope in for_subject_scope:
            key = (
                content_types[type(subject)],
                subject.id,
                content_types[type(scope)],
                scope.id,
            )

            if key in role_assignments_by_user_id_scope_id:
                roles_by_user_scope[
                    (subject, scope)
                ] = role_assignments_by_user_id_scope_id[key]
            else:
                roles_by_user_scope[(subject, scope)] = None

        return roles_by_user_scope

    def get_roles_per_scope(
        self, workspace: Workspace, actor: AbstractUser, include_trash=False
    ) -> List[Tuple[ScopeObject, List[Role]]]:
        """
        Returns the RoleAssignments for the given actor in the given workspace. The
        roles are ordered by position of the role scope in the object hierarchy: the
        highest parent is before the lowest.

        :param workspace: The workspace the RoleAssignments belong to.
        :param actor: The actor for whom we want the RoleAssignments for.
        :param include_trash: If true then also checks even if given workspace has been
            trashed instead of raising a DoesNotExist exception.
        :return: A list of tuple containing the scope and the role ordered by scope.
            The higher a scope is high in the object hierarchy, the higher the tuple in
            the list.
        """

        actor_subject_type = subject_type_registry.get_by_model(actor)
        actor_cache_key = (
            f"{actor_subject_type.type}_{actor.id}_{workspace.id}_{include_trash}"
        )

        def _get_roles_per_scope():
            return self.get_roles_per_scope_for_actors(
                workspace, actor_subject_type, [actor], include_trash=include_trash
            )[actor]

        return local_cache.get(
            f"{ROLE_ASSIGNMENT_CACHE_KEY_PREFIX}_get_roles_per_scope_{actor_cache_key}",
            _get_roles_per_scope,
        )

    def get_roles_per_scope_for_actors(
        self,
        workspace: Workspace,
        actor_subject_type: SubjectType,
        actors: List[Subject],
        include_trash=False,
    ) -> Dict[Subject, Tuple[ScopeObject, List[Role]]]:
        """
        Returns the role assignments for for all given actors who are all of the
        actor_subject_type.

        :param workspace: The workspace in which we want the role assignments for.
        :param actor_subject_type: The type of the actors.
        :param actors: The actors we want the role per scope map.
        :return: A dict with actor as keys and a list of (scope, list[role]) as value.
            The roles per scope are sorted by priority: the more the scope is high in
            the object hierarchy, the earlier the tuple is in the list.
        """

        content_types = ContentType.objects.get_for_models(
            actor_subject_type.model_class, Team, Workspace
        )

        actor_by_id = {a.id: a for a in actors}

        subjects_q = Q(
            subject_type=content_types[actor_subject_type.model_class],
            subject_id__in=actor_by_id.keys(),
        )

        # Add team roles
        users_teams_qs = TeamSubject.objects.filter(
            subject_type=content_types[actor_subject_type.model_class],
            subject_id__in=actor_by_id.keys(),
        )

        actors_cache_key = (
            f"{actor_subject_type.type}_{'_'.join([str(a.id) for a in actors])}"
        )

        def _get_teams_subjects():
            return users_teams_qs.values_list("team_id", "subject_id")

        teams_subjects = local_cache.get(
            f"{ROLE_ASSIGNMENT_CACHE_KEY_PREFIX}_{actors_cache_key}",
            _get_teams_subjects,
        )

        # Populate double map for later use
        subjects_per_team = defaultdict(list)
        teams_per_subject = defaultdict(list)
        for team_id, subject_id in teams_subjects:
            subjects_per_team[team_id].append(subject_id)
            teams_per_subject[subject_id].append(team_id)

        subjects_q |= Q(
            subject_type=content_types[Team],
            subject_id__in=subjects_per_team.keys(),
        )

        # Allow to order assignment by scope level
        scope_cases = [
            When(
                scope_type=ContentType.objects.get_for_model(scope_type.model_class),
                then=Value(scope_type.level),
            )
            for scope_type in [
                object_scope_type_registry.get(name)
                for name in ROLE_ASSIGNABLE_OBJECT_MAP
            ]
            if scope_type.type != CoreObjectScopeType.type
        ]

        # Allow to order assignment by subject priority
        role_priority_cases = [
            When(
                subject_type=content_types[subject_type.model_class],
                then=Value(order),
            )
            for order, subject_type in enumerate(
                [
                    subject_type_registry.get(subject_name)
                    for subject_name in ALLOWED_SUBJECT_TYPE_BY_PRIORITY
                ]
            )
        ]

        # Final query
        def _get_role_assignments():
            return (
                RoleAssignment.objects.filter(
                    workspace=workspace,
                )
                .filter(subjects_q, ~Q(role__uid=NO_ROLE_LOW_PRIORITY_ROLE_UID))
                .annotate(
                    scope_type_order=Case(
                        *scope_cases,
                        default=Value(0),
                        output_field=IntegerField(),
                    ),
                    role_priority=Case(
                        *role_priority_cases,
                        default=Value(0),
                        output_field=IntegerField(),
                    ),
                )
                .order_by(
                    "scope_type_order", "scope_id", "role_priority", "subject_id", "id"
                )
                .select_related("subject_type")
            )

        role_assignments = local_cache.get(
            f"{ROLE_ASSIGNMENT_CACHE_KEY_PREFIX}_{workspace.id}_{actors_cache_key}",
            _get_role_assignments,
        )

        workspace_scope_param = (content_types[Workspace].id, workspace.id)

        # Track the latest role priority for each scope of each subject
        priorities_by_scope_per_actor_id = defaultdict(dict)

        # Keep a list of scope params to query later
        scopes_to_query = defaultdict(set)

        roles_by_scope = defaultdict(lambda: {workspace_scope_param: []})

        for role_assignment in role_assignments:
            scope_param = (role_assignment.scope_type_id, role_assignment.scope_id)
            role = self.get_role_by_id(role_assignment.role_id)
            role_assignment_priority = role_assignment.role_priority
            subject_id = role_assignment.subject_id

            scopes_to_query[role_assignment.scope_type_id].add(role_assignment.scope_id)

            # Is it a simple actor or a team?
            # If it's a team we need to iterate over all the actor that are
            # subject of the team
            if role_assignment.subject_type == content_types[Team]:
                actor_ids = subjects_per_team[subject_id]
            else:
                actor_ids = [subject_id]

            for actor_id in actor_ids:
                if not roles_by_scope[actor_id].get(scope_param, []):
                    # If there is no role yet for the scope of the role assignment
                    # We can define one from the assignment.
                    # We don't use defaultdict here to be sure we have the right key
                    # order for role_by_scope. We need to keep it ordered as expected
                    # by the caller.
                    roles_by_scope[actor_id][scope_param] = [role]
                    priorities_by_scope_per_actor_id[actor_id][
                        scope_param
                    ] = role_assignment_priority
                else:
                    # If the priority is the same we add the role to the
                    # current role list.
                    # Otherwise, we ignore the role as the following roles can only
                    # have a lower priority because of the priority ordering
                    current_priority = priorities_by_scope_per_actor_id[actor_id][
                        scope_param
                    ]
                    if (
                        current_priority == role_assignment_priority
                        and role not in roles_by_scope[actor_id][scope_param]
                    ):
                        roles_by_scope[actor_id][scope_param].append(role)

        # For user actor, we need to get the workspace level role by reading the
        # WorkspaceUser permissions property
        if actor_subject_type.type == UserSubjectType.type:
            # Get all workspace users at once
            actor_ids_set = {a.id for a in actors}

            def _get_user_permissions_by_id():
                if include_trash:
                    wp_users = WorkspaceUser.objects_and_trash.filter(
                        workspace_id=workspace.id, user_id__in=actor_ids_set
                    )
                else:
                    wp_users = workspace.workspaceuser_set.all()
                return {
                    wu.user_id: wu.permissions
                    for wu in wp_users
                    if wu.user_id in actor_ids_set
                }

            user_permissions_by_id = local_cache.get(
                f"{ROLE_ASSIGNMENT_CACHE_KEY_PREFIX}_{workspace.id}_{actors_cache_key}_{include_trash}",
                _get_user_permissions_by_id,
            )

            for actor in actors:
                workspace_level_role = self.get_role_by_uid(
                    user_permissions_by_id.get(actor.id, NO_ACCESS_ROLE_UID),
                    use_fallback=True,
                )
                if workspace_level_role.uid == NO_ROLE_LOW_PRIORITY_ROLE_UID:
                    # Low priority role -> Use team role or NO_ACCESS if no team role
                    if not roles_by_scope[actor.id].get(workspace_scope_param):
                        roles_by_scope[actor.id][workspace_scope_param] = [
                            self.get_role_by_uid(NO_ACCESS_ROLE_UID)
                        ]
                else:
                    # Otherwise user role wins
                    roles_by_scope[actor.id][workspace_scope_param] = [
                        workspace_level_role
                    ]

        # Populate scope cache by querying all scopes type by type
        scope_cache = {workspace_scope_param: workspace}
        for content_type_id, content_ids in scopes_to_query.items():
            for scope in self.get_scopes(content_type_id, content_ids):
                scope_cache[(content_type_id, scope.id)] = scope

        # Finally replace scope_params by real scope
        roles_per_scope_per_user = defaultdict(list)
        for actor in actors:
            for key, value in roles_by_scope[actor.id].items():
                # scope_cache contains all the filtered scopes we need to check
                # permissions for. Objects from snapshotted applications (table,
                # applications, etc.) are filtered out as they're not accessible to the
                # user, so we can safely ignore them here.
                if key not in scope_cache:
                    continue
                roles_per_scope_per_user[actor].append((scope_cache[key], value))

        return roles_per_scope_per_user

    def get_computed_roles(
        self, roles_per_scopes, context: Any, cache: Optional[Dict] = None
    ) -> List[Role]:
        """
        Returns the computed roles for the given actor on the given context.

        :param roles_per_scopes: The roles that the user has per scope object.
        :param context: The context on which we want to now the role.
        :param cache: A cache dict to temporarily store reusable values in.
        :return: A list of roles that applies on this context.
        """

        most_precise_roles = [self.get_role_by_uid(NO_ACCESS_ROLE_UID)]

        cache = cache or {}

        def scope_includes_context(scope, context):
            key = (type(scope).__name__, scope.id, type(context).__name__, context.id)
            if key not in cache:
                cache[key] = object_scope_type_registry.scope_includes_context(
                    scope, context
                )
            return cache[key]

        for scope, roles in roles_per_scopes:
            if scope_includes_context(scope, context):
                # Check if this scope includes the context. As the role assignments
                # are sorted, the new scope is more precise than the previous one.
                # So we keep this new role.
                most_precise_roles = list(roles)
            elif scope_includes_context(context, scope) and any(
                [r.uid != NO_ACCESS_ROLE_UID for r in roles]
            ):
                # Here the user has a permission on a scope that is a child of the
                # context, then we grant the user permission on all read operations
                # for all parents of that scope and hence this context should be
                # readable.
                # For example, if you have a "BUILDER" role on only a table scope,
                # and the context here is the parent database of this table the
                # user should be able to read this database object so they can
                # actually have access to lower down.
                most_precise_roles.append(self.get_role_by_uid(READ_ONLY_ROLE_UID))

        return most_precise_roles

    @clear_roles_from_local_cache()
    def assign_role(
        self, subject, workspace, role=None, scope=None, send_signals: bool = True
    ) -> Optional[RoleAssignment]:
        """
        Assign a role to a subject in the context of the given workspace over a
        specified scope.

        :param subject: The subject targeted by the role.
        :param workspace: The workspace in which we want to assign the role.
        :param role: The role we want to assign. If the role is `None` then we remove
            the current role of the subject in the workspace for the given scope.
        :param scope: An optional scope on which the role applies. If no scope is given
            the workspace is used as scope.
        :return: The created RoleAssignment if role is not `None` else `None`.
        :param send_signals: By default a `role_assignment_{created,update}` signal is
            fire when a RoleAssignment is saved. Set this to `False` to prevent signals
            from firing, and the end-user receiving a "Permissions updated" message.
        """

        if scope is None:
            scope = workspace

        if role is None:
            # Early return, we are removing the current role.
            self.remove_role(subject, workspace, scope=scope)
            return

        content_types = ContentType.objects.get_for_models(scope, subject)

        # Workspace level permissions are not stored as RoleAssignment records but
        # in the WorkspaceUser.permissions property.
        if RoleAssignmentHandler.is_workspace_level_assignment(
            workspace, scope, subject
        ):
            workspace_user = workspace.get_workspace_user(subject)
            new_permissions = "MEMBER" if role.uid == "BUILDER" else role.uid
            CoreHandler().force_update_workspace_user(
                None, workspace_user, permissions=new_permissions
            )

            # We need to fake a RoleAssignment instance here to keep the same
            # return interface
            return RoleAssignment(
                subject=subject,
                subject_id=subject.id,
                subject_type=content_types[subject],
                role=role,
                workspace=workspace,
                scope=scope,
                scope_type=content_types[scope],
            )

        role_assignment, created = RoleAssignment.objects.update_or_create(
            subject_id=subject.id,
            subject_type=content_types[subject],
            workspace=workspace,
            scope_id=scope.id,
            scope_type=content_types[scope],
            defaults={"role": role},
        )

        if send_signals:
            # TODO remove signaling from here
            if created:
                role_assignment_created.send(
                    self, subject=subject, workspace=workspace, scope=scope, role=role
                )
            else:
                role_assignment_updated.send(
                    self, subject=subject, workspace=workspace, scope=scope, role=role
                )

        return role_assignment

    @clear_roles_from_local_cache()
    def remove_role(
        self, subject: Union[AbstractUser, Team], workspace: Workspace, scope=None
    ):
        """
        Remove the role of a subject in the context of the given workspace over a
        specified scope.

        :param subject: The subject for whom we want to remove the role for.
        :param workspace: The workspace in which we want to remove the role.
        :param scope: An optional scope on which the existing role applied.
            If no scope is given the workspace is used as scope.
        """

        if scope is None:
            scope = workspace

        if RoleAssignmentHandler.is_workspace_level_assignment(
            workspace, scope, subject
        ):
            workspace_user = workspace.get_workspace_user(subject)
            new_permissions = NO_ACCESS_ROLE_UID
            CoreHandler().force_update_workspace_user(
                None, workspace_user, permissions=new_permissions
            )
            return

        content_types = ContentType.objects.get_for_models(scope, subject)

        RoleAssignment.objects.filter(
            subject_id=subject.id,
            subject_type=content_types[subject],
            workspace=workspace,
            scope_id=scope.id,
            scope_type=content_types[scope],
        ).delete()
        role_assignment_deleted.send(
            self, subject=subject, workspace=workspace, scope=scope
        )

    def assign_role_batch(
        self,
        workspace: Workspace,
        new_role_assignments: List[NewRoleAssignment],
        send_signals: bool = True,
    ):
        """
        TODO: this function is not yet a real batch. Should be implemented properly.

        Creates role assignments in batch, this should be used if many role assignments
        are created at once, to be more efficient.

        :return: The list of role assignments. Some can be None if the role assignment
            has been deleted.
        """

        return [
            self.assign_role(
                role_assignment.subject,
                workspace,
                role=role_assignment.role,
                scope=role_assignment.scope,
                send_signals=send_signals,
            )
            for role_assignment in new_role_assignments
        ]

    def assign_role_batch_for_user(
        self,
        user: AbstractUser,
        workspace: Workspace,
        new_role_assignments: List[NewRoleAssignment],
    ) -> List[Optional[RoleAssignment]]:
        """
        Assign multiple roles to multiple users at once. This method do all the Licence
        and permission checking before calling the real batch assign.

        :param user: The user who assigns roles.
        :param workspace: The workspace in which the role assignments take place.
        :param new_role_assignments: A list of triplet (subject, role_uid, scope) for
            each assignment the user wants to do.
        :raise SubjectNotExist: If at least one of the subjects is not member of the
            workspace.
        :raise SubjectUnsupported: If at least one of the subjects is unsupported by
            role assignments.
        :raise ScopeNotExist: If at least one of the scopes is not a child of the
            workspace.
        :return: A list of the result of each assignment. Each result can be a
            RoleAssignment object or None if the assignment has been removed.
        """

        # First check licence
        LicenseHandler.raise_if_user_doesnt_have_feature(RBAC, user, workspace)

        # Create a dict of unique scope and subject by type to allow performants
        # preliminary checks
        permission_to_check = []
        unique_scopes_by_type = defaultdict(set)
        unique_subjects_by_type = defaultdict(set)
        for subject, _, scope in new_role_assignments:
            scope_type = object_scope_type_registry.get_by_model(scope)
            if scope not in unique_scopes_by_type[scope_type]:
                permission_to_check.append(
                    PermissionCheck(
                        user,
                        ROLE_ASSIGNABLE_OBJECT_MAP[scope_type.type]["UPDATE"],
                        context=scope,
                    )
                )
                unique_scopes_by_type[scope_type].add(scope)
                subject_type = subject_type_registry.get_by_model(subject)
                unique_subjects_by_type[subject_type].add(subject)

        # Check if all subjects are in the workspace
        for subject_type, subjects in unique_subjects_by_type.items():
            if subject_type.type not in ALLOWED_SUBJECT_TYPE_BY_PRIORITY:
                raise SubjectUnsupported(
                    f"The subject type {subject_type.type} is unsupported for role "
                    "assignments."
                )
            are_subjects_in_workspace = subject_type.are_in_workspace(
                subjects, workspace
            )
            if not all(are_subjects_in_workspace):
                raise SubjectNotExist()

        # Check if all scopes are child of the workspace
        for scope_type, scopes in unique_scopes_by_type.items():
            are_scopes_in_workspace = scope_type.are_objects_child_of(scopes, workspace)
            if not all(are_scopes_in_workspace):
                raise ScopeNotExist()

        # Do we have the permission to change roles for all scopes
        user_permission_for_scopes = CoreHandler().check_multiple_permissions(
            permission_to_check,
            workspace=workspace,
        )

        if not all(user_permission_for_scopes.values()):
            raise PermissionDenied()

        return self.assign_role_batch(workspace, new_role_assignments)

    def get_scopes(self, content_type_id, scope_ids) -> QuerySet[ScopeObject]:
        """
        Helper method that returns the actual scope object given the scope ID and
        the scope type.

        :param scope_id: The scope id.
        :param content_type_id: The content_type id
        :return: A QuerySet of the scope objects matching the given scope IDs.
        """

        content_type = ContentType.objects.get_for_id(content_type_id)
        object_scope = object_scope_type_registry.get_for_class(
            content_type.model_class()
        )
        return object_scope.get_enhanced_queryset(include_trash=True).filter(
            id__in=scope_ids
        )

    def get_role_assignments(self, workspace: Workspace, scope: Optional[ScopeObject]):
        """
        Helper method that returns all role assignments given a scope and workspace.

        :param workspace: The workspace that the scope belongs to
        :param scope: The scope used for filtering role assignments
        """

        if isinstance(scope, Workspace) and scope.id == workspace.id:
            workspace_users = WorkspaceUser.objects.filter(workspace=workspace)

            role_assignments = []

            for workspace_user in workspace_users:
                role_uid = workspace_user.permissions
                role = self.get_role_by_uid(role_uid, use_fallback=True)
                subject = workspace_user.user

                content_types = ContentType.objects.get_for_models(scope, subject)

                # We need to fake a RoleAssignment instance here to keep the same
                # return interface
                role_assignments.append(
                    RoleAssignment(
                        subject=subject,
                        subject_id=subject.id,
                        subject_type=content_types[subject],
                        role=role,
                        workspace=workspace,
                        scope=scope,
                        scope_type=content_types[scope],
                    )
                )
            return role_assignments
        else:
            qs = self._get_role_assignments_for_valid_subjects_qs()
            role_assignments = qs.filter(
                workspace=workspace,
                scope_id=scope.id,
                scope_type=ContentType.objects.get_for_model(scope),
            )
            return list(role_assignments)

    @classmethod
    def is_workspace_level_assignment(
        cls, workspace: Workspace, scope: ScopeObject, subject: Subject
    ):
        return (
            scope == workspace
            and scope.id == workspace.id
            and isinstance(subject, User)
        )
