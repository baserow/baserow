from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import JSONField, OuterRef, Value
from django.db.models.functions import JSONObject

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.core.action.registries import action_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.identities.exceptions import IdentityCannotBeScoped
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.registries import IdentityExtensionType
from baserow.core.models import Application, User, Workspace
from baserow.core.object_scopes import ApplicationObjectScopeType
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.registries import object_scope_type_registry
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import RBAC, TEAMS
from baserow_enterprise.role.actions import BatchAssignRoleActionType
from baserow_enterprise.role.constants import (
    ADMIN_ROLE_UID,
    BUILDER_ROLE_UID,
    COMMENTER_ROLE_UID,
    EDITOR_ROLE_UID,
    NO_ACCESS_ROLE_UID,
    VIEWER_ROLE_UID,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment
from baserow_enterprise.role.operations import (
    ReadRoleApplicationOperationType,
    UpdateRoleApplicationOperationType,
)
from baserow_enterprise.role.types import NewRoleAssignment
from baserow_enterprise.teams.actions import (
    CreateTeamSubjectActionType,
    DeleteTeamSubjectActionType,
)
from baserow_enterprise.teams.models import Team, TeamSubject
from baserow_enterprise.teams.operations import (
    CreateTeamSubjectOperationType,
    DeleteTeamSubjectOperationType,
)
from baserow_premium.license.handler import LicenseHandler

# The roles an identity scoped to applications can have on one of them. The admin
# role is only given by an installer who may change the roles of the application,
# and is the builder role otherwise.
SCOPED_IDENTITY_ROLE_UIDS = [
    VIEWER_ROLE_UID,
    COMMENTER_ROLE_UID,
    EDITOR_ROLE_UID,
    BUILDER_ROLE_UID,
    ADMIN_ROLE_UID,
]
# The roles of a workspace without roles on applications, as the role that gives
# the same on an application.
WORKSPACE_ROLE_ALIASES = {"MEMBER": BUILDER_ROLE_UID}


class IdentityTeamSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


@extend_schema_field(IdentityTeamSummarySerializer(many=True))
class IdentityTeamsField(serializers.Field):
    def to_representation(self, identity):
        # List querysets annotate this after one license check for the whole page.
        if hasattr(identity, "_identity_teams"):
            return identity._identity_teams
        if not LicenseHandler.workspace_has_feature(
            TEAMS, IdentityHandler().get_workspace(identity)
        ):
            return []
        return list(
            Team.objects.filter(
                subjects__subject_type=ContentType.objects.get_for_model(User),
                subjects__subject_id=identity.id,
            ).values("id", "name")
        )


class EnterpriseIdentityExtensionType(IdentityExtensionType):
    type = "enterprise_permissions"
    request_fields = {
        "team_ids": serializers.ListField(
            child=serializers.IntegerField(), required=False
        )
    }
    response_fields = {"teams": IdentityTeamsField(source="*", read_only=True)}
    list_response_fields = {
        "role_assignment_count": serializers.IntegerField(
            read_only=True,
            required=False,
            help_text="Enterprise or advanced only: the number of roles this identity "
            "holds on databases, tables and restricted views whose roles the "
            "requesting user may read.",
        )
    }

    def enhance_queryset(self, queryset, workspace):
        """Load team summaries with the Identities instead of querying each Identity."""

        if not LicenseHandler.workspace_has_feature(TEAMS, workspace):
            # Keep the annotation so serialization does not repeat the feature
            # check for every identity in a disabled workspace.
            return queryset.annotate(
                _identity_teams=Value([], output_field=JSONField())
            )
        teams = (
            Team.objects.filter(
                subjects__subject_type=ContentType.objects.get_for_model(User),
                subjects__subject_id=OuterRef("pk"),
            )
            .annotate(summary=JSONObject(id="id", name="name"))
            .values("summary")
        )
        return queryset.annotate(_identity_teams=ArraySubquery(teams))

    def role_uid_exists(self, role_uid, workspace):
        """Validate selectable roles using the same aliases as role resolution."""
        if not LicenseHandler.workspace_has_feature(RBAC, workspace):
            return role_uid in {"ADMIN", "MEMBER"}
        # Use the permission resolver so aliases such as MEMBER -> BUILDER have
        # the same meaning during validation and permission checks.
        try:
            role = RoleAssignmentHandler().get_role_by_uid(role_uid)
        except Role.DoesNotExist:
            return False
        return not role.hidden and role.workspace_id in (None, workspace.id)

    def get_default_role_uid(self, workspace):
        if LicenseHandler.workspace_has_feature(RBAC, workspace):
            return "NO_ACCESS"
        return None

    def can_scope_to_applications(self, user, workspace):
        """With roles, an identity can have no access except on some applications."""

        return LicenseHandler.user_has_feature(RBAC, user, workspace)

    def scope_to_applications(self, identity, applications, user, roles):
        """
        Gives the identity the given role on each application. The user must be
        allowed to change every application that gets one, so the identity never
        gets more than them: the admin role is given only on the applications
        whose roles the user may change, and the builder role on the others.
        Without roles it keeps no access, and its tools are checked against that
        when they run. The assignments are recorded like those of the role
        endpoints, so they show in the audit log.
        """

        workspace = IdentityHandler().get_workspace(identity)
        # A new identity has no access with roles. Scoping one that has more would
        # leave it access to the whole workspace.
        if IdentityHandler.get_role_uid(identity) != NO_ACCESS_ROLE_UID:
            raise IdentityCannotBeScoped(
                "Only an identity without access can be scoped."
            )
        role_uids = {
            application_id: WORKSPACE_ROLE_ALIASES.get(role_uid, role_uid)
            for application_id, role_uid in roles
        }
        role_uids = {
            application_id: role_uid
            for application_id, role_uid in role_uids.items()
            if role_uid in SCOPED_IDENTITY_ROLE_UIDS
        }
        # Roles on applications are stored for the base model, which the role
        # endpoints resolve the `application` scope to.
        scopes = list(
            Application.objects.filter(
                workspace=workspace,
                id__in=[
                    application.id
                    for application in applications
                    if application.id in role_uids
                ],
            ).order_by("id")
        )
        if not scopes:
            return
        # Roles on an application are checked against its specific type.
        CoreHandler().check_multiple_permissions(
            [
                PermissionCheck(
                    user, UpdateApplicationOperationType.type, scope.specific
                )
                for scope in scopes
            ],
            workspace=workspace,
            raise_exception=True,
        )
        admin_scopes = [
            scope for scope in scopes if role_uids[scope.id] == ADMIN_ROLE_UID
        ]
        if admin_scopes:
            can_change_roles = CoreHandler().check_multiple_permissions(
                [
                    PermissionCheck(
                        user, UpdateRoleApplicationOperationType.type, scope.specific
                    )
                    for scope in admin_scopes
                ],
                workspace=workspace,
            )
            for check, allowed in can_change_roles.items():
                if allowed is not True:
                    role_uids[check.context.id] = BUILDER_ROLE_UID
        role_by_uid = {
            role.uid: role
            for role in Role.objects.filter(uid__in=set(role_uids.values()))
        }
        action_type_registry.get_by_type(BatchAssignRoleActionType).do(
            user,
            [
                NewRoleAssignment(identity, role_by_uid[role_uids[scope.id]], scope)
                for scope in scopes
            ],
            workspace,
            check_role_permissions=False,
        )

    def get_application_roles(self, identity):
        """
        Exports the roles of an identity on single applications. An application
        with a role that can't be given on one, or whose tables or views have
        roles, or where a team of the identity has a say, is exported as one it
        can't access, so the new identity never gets more than the exported one.
        """

        workspace = IdentityHandler().get_workspace(identity)
        if not LicenseHandler.workspace_has_feature(RBAC, workspace):
            return None
        user_type = ContentType.objects.get_for_model(User)
        application_type = ContentType.objects.get_for_model(Application)
        identity_assignments = RoleAssignment.objects.filter(
            workspace=workspace, subject_type=user_type, subject_id=identity.id
        )
        roles = {
            application_id: role_uid
            if role_uid in SCOPED_IDENTITY_ROLE_UIDS
            else NO_ACCESS_ROLE_UID
            for application_id, role_uid in identity_assignments.filter(
                scope_type=application_type
            ).values_list("scope_id", "role__uid")
        }
        team_assignments = RoleAssignment.objects.filter(
            workspace=workspace,
            subject_type=ContentType.objects.get_for_model(Team),
            subject_id__in=TeamSubject.objects.filter(
                subject_type=user_type, subject_id=identity.id
            ).values("team_id"),
        )
        # A role on a table or view of an application changes what the role on the
        # application gives, also when a team of the identity has it. So does the
        # role of a team on an application where the identity has none.
        narrowed = self._applications_of(
            identity_assignments.exclude(scope_type=application_type)
        ) | self._applications_of(team_assignments.exclude(scope_type=application_type))
        narrowed |= set(
            team_assignments.filter(scope_type=application_type)
            .exclude(scope_id__in=roles)
            .values_list("scope_id", flat=True)
        )
        roles.update(
            {application_id: NO_ACCESS_ROLE_UID for application_id in narrowed}
        )
        return sorted(roles.items())

    def _applications_of(self, assignments) -> set[int]:
        """
        :param assignments: Role assignments on scopes other than an application.
        :return: The ids of the applications that contain one of their scopes.
        """

        application_scope_type = object_scope_type_registry.get(
            ApplicationObjectScopeType.type
        )
        application_ids = set()
        for assignment in assignments.prefetch_related("scope"):
            scope = assignment.scope
            if scope is None or isinstance(scope, Workspace):
                continue
            application = object_scope_type_registry.get_parent(
                scope, at_scope_type=application_scope_type
            )
            if application is not None:
                application_ids.add(application.id)
        return application_ids

    def filter_readable_application_roles(self, roles, user, workspace):
        """Keeps the roles on applications of the workspace whose roles the user may read."""

        # Without roles on applications, there's nothing to hide.
        if not LicenseHandler.workspace_has_feature(RBAC, workspace):
            return roles
        readable = CoreHandler().check_multiple_permissions(
            [
                PermissionCheck(
                    user, ReadRoleApplicationOperationType.type, scope.specific
                )
                for scope in Application.objects.filter(
                    workspace=workspace, id__in=[role[0] for role in roles]
                )
            ],
            workspace=workspace,
        )
        allowed = {
            check.context.id for check, result in readable.items() if result is True
        }
        return [role for role in roles if role[0] in allowed]

    def annotate_serialized_identities(
        self, workspace, identities, serialized_identities, user
    ):
        """
        Annotates every identity with the number of roles it holds on databases, tables
        and restricted views, as listed by the subject role assignments endpoint.
        """

        counts = RoleAssignmentHandler().count_subject_role_assignments(
            user, workspace, list(identities)
        )
        if counts:
            for identity, serialized_identity in zip(identities, serialized_identities):
                serialized_identity["role_assignment_count"] = counts[identity]
        return serialized_identities

    def _sync_teams(self, identity, team_ids, user):
        """Authorize all membership changes before replacing an identity's teams."""

        if team_ids is None:
            return
        LicenseHandler.raise_if_user_doesnt_have_feature(
            TEAMS, user, IdentityHandler().get_workspace(identity)
        )
        teams = list(
            Team.objects.filter(
                id__in=set(team_ids),
                workspace=IdentityHandler().get_workspace(identity),
            )
        )
        if len(teams) != len(set(team_ids)):
            raise ValidationError(
                {"team_ids": "Every team must belong to the identity's workspace."}
            )
        subject_type = ContentType.objects.get_for_model(User)
        memberships = list(
            TeamSubject.objects.filter(
                subject_type=subject_type, subject_id=identity.id
            ).select_related("team__workspace")
        )
        existing_ids = {membership.team_id for membership in memberships}
        added_teams = [team for team in teams if team.id not in existing_ids]
        removed_memberships = [
            membership
            for membership in memberships
            if membership.team_id not in team_ids
        ]
        # Match the team-subject endpoints' scopes and authorize the whole diff
        # before writing. Retained memberships require no extra permissions.
        checks = [
            PermissionCheck(user, CreateTeamSubjectOperationType.type, team)
            for team in added_teams
        ] + [
            PermissionCheck(user, DeleteTeamSubjectOperationType.type, membership)
            for membership in removed_memberships
        ]
        CoreHandler().check_multiple_permissions(
            checks,
            workspace=IdentityHandler().get_workspace(identity),
            raise_exception=True,
        )
        TeamSubject.objects.filter(
            id__in=[membership.id for membership in removed_memberships]
        ).delete()
        added_memberships = TeamSubject.objects.bulk_create(
            [TeamSubject(team=team, subject=identity) for team in added_teams]
        )
        self._record_team_changes(
            user, identity, added_memberships, removed_memberships
        )

    def _record_team_changes(
        self,
        user: AbstractUser,
        identity: User,
        added: list[TeamSubject],
        removed: list[TeamSubject],
    ) -> None:
        """
        Records the teams an identity joined and left as the actions the team
        endpoints register, so the audit log shows them wherever they are made.

        :param user: The user who changed the teams of the identity.
        :param identity: The identity whose teams changed.
        :param added: The memberships that were created.
        :param removed: The memberships that were deleted.
        """

        workspace = IdentityHandler().get_workspace(identity)
        created = action_type_registry.get_by_type(CreateTeamSubjectActionType)
        for membership in added:
            created.register_action(
                user=user,
                params=created.Params(
                    membership.team_id,
                    membership.team.name,
                    membership.id,
                    {"id": identity.id},
                    membership.subject_type_natural_key,
                ),
                scope=created.scope(workspace.id),
                workspace=workspace,
            )
        deleted = action_type_registry.get_by_type(DeleteTeamSubjectActionType)
        for membership in removed:
            deleted.register_action(
                user=user,
                params=deleted.Params(
                    membership.team_id,
                    membership.team.name,
                    membership.id,
                    identity.id,
                    membership.subject_type_natural_key,
                ),
                scope=deleted.scope(workspace.id),
                workspace=workspace,
            )

    def create(self, identity, values, user):
        self._sync_teams(identity, values.get("team_ids"), user)

    def update(self, identity, values, user):
        self._sync_teams(identity, values.get("team_ids"), user)
