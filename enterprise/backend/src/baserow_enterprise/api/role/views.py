from typing import Any, Dict
from urllib.request import Request

from django.contrib.auth import get_user_model
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.captcha.errors import ERROR_CAPTCHA_VERIFICATION_FAILED
from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.schemas import get_error_schema
from baserow.api.workspaces.invitation_links.errors import (
    ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST,
    ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED,
)
from baserow.api.workspaces.users.errors import ERROR_GROUP_USER_ALREADY_EXISTS
from baserow.core.action.registries import action_type_registry
from baserow.core.captcha.exceptions import CaptchaVerificationFailed
from baserow.core.captcha.handler import CaptchaHandler
from baserow.core.exceptions import (
    LastAdminOfWorkspace,
    ObjectScopeTypeDoesNotExist,
    SubjectTypeNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceInvitationLinkDoesNotExist,
    WorkspaceInvitationLinkSignupsDisabled,
    WorkspaceUserAlreadyExists,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.registries import object_scope_type_registry
from baserow.core.types import PermissionCheck
from baserow.core.utils import (
    get_user_remote_ip_address_from_request,
    unique_dicts_in_list,
)
from baserow.throttling.handler import WorkspaceInvitationRateThrottle
from baserow_enterprise.api.errors import (
    ERROR_CANT_ASSIGN_ROLE_TO_SELF,
    ERROR_DUPLICATE_ROLE_ASSIGNMENTS,
    ERROR_LAST_ADMIN_OF_GROUP,
    ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
    ERROR_ROLE_DOES_NOT_EXIST,
    ERROR_SCOPE_DOES_NOT_EXIST,
    ERROR_SCOPED_INVITATION_DOES_NOT_EXIST,
    ERROR_SUBJECT_DOES_NOT_EXIST,
    ERROR_SUBJECT_TYPE_DOES_NOT_EXIST,
    ERROR_SUBJECT_TYPE_UNSUPPORTED,
)
from baserow_enterprise.exceptions import (
    CannotAssignRoleToSelf,
    RoleNotExist,
    ScopedInvitationDoesNotExist,
    ScopeNotExist,
    SubjectNotExist,
    SubjectUnsupported,
)
from baserow_enterprise.features import RBAC
from baserow_enterprise.role.actions import (
    BatchAssignRoleActionType,
    CreateScopedInvitationActionType,
    CreateScopedInvitationLinkActionType,
    DeleteScopedInvitationActionType,
    DeleteScopedInvitationLinkActionType,
    UpdateScopedInvitationActionType,
    UpdateScopedInvitationLinkActionType,
)
from baserow_enterprise.role.constants import ROLE_ASSIGNABLE_OBJECT_MAP
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.types import NewRoleAssignment
from baserow_enterprise.teams.operations import ListTeamSubjectsOperationType
from baserow_premium.license.handler import LicenseHandler

from .exceptions import DuplicateRoleAssignments
from .serializers import (
    BatchCreateRoleAssignmentSerializer,
    CreateRoleAssignmentSerializer,
    CreateScopedInvitationLinkSerializer,
    CreateScopedInvitationSerializer,
    EffectiveAccessSerializer,
    GetRoleAssignmentsQueryParametersSerializer,
    OpenApiRoleAssignmentSerializer,
    RoleAssignmentSerializer,
    ScopedInvitationLinkSerializer,
    ScopedInvitationSerializer,
    UpdateScopedInvitationLinkSerializer,
    UpdateScopedInvitationSerializer,
)

User = get_user_model()


class RoleAssignmentsView(APIView):
    """Views to assign a role."""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace in which the role assignment takes place.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="assign_role",
        description=(
            "You can assign a role to a subject into the given workspace for the given "
            "scope with this endpoint. If you want to remove the role you can "
            "omit the role property."
        ),
        request=CreateRoleAssignmentSerializer,
        responses={
            200: OpenApiRoleAssignmentSerializer,
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_CANT_ASSIGN_ROLE_EXCEPTION_TO_ADMIN",
                    "ERROR_CANT_ASSIGN_ROLE_TO_SELF",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
                    "ERROR_SUBJECT_TYPE_DOES_NOT_EXIST",
                    "ERROR_ROLE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ObjectScopeTypeDoesNotExist: ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
            SubjectTypeNotExist: ERROR_SUBJECT_TYPE_DOES_NOT_EXIST,
            SubjectNotExist: ERROR_SUBJECT_DOES_NOT_EXIST,
            SubjectUnsupported: ERROR_SUBJECT_TYPE_UNSUPPORTED,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            RoleNotExist: ERROR_ROLE_DOES_NOT_EXIST,
            LastAdminOfWorkspace: ERROR_LAST_ADMIN_OF_GROUP,
            CannotAssignRoleToSelf: ERROR_CANT_ASSIGN_ROLE_TO_SELF,
        }
    )
    @validate_body(CreateRoleAssignmentSerializer, return_validated=True)
    @transaction.atomic
    def post(
        self,
        request: Request,
        workspace_id: int,
        data,
    ) -> Response:
        """Assign or remove a role to the user on the given scope."""

        workspace = CoreHandler().get_workspace(workspace_id)

        role = data.get("role", None)
        subject = data.get("subject", None)
        scope = data.get("scope", None)

        new_role_assignments = [NewRoleAssignment(subject, role, scope)]

        roles_assignments = action_type_registry.get_by_type(
            BatchAssignRoleActionType
        ).do(
            request.user,
            new_role_assignments,
            workspace,
        )

        role_assignment = roles_assignments[0]

        if role_assignment:
            RoleAssignmentHandler().prefetch_role_assignment_subjects([role_assignment])
            serializer = RoleAssignmentSerializer(role_assignment)
            return Response(serializer.data)

        return Response(status=204)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace in which the role assignments are related to.",
            ),
            OpenApiParameter(
                name="scope_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The id of the scope you are trying to get all role"
                "assignments for.",
            ),
            OpenApiParameter(
                name="scope_type",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The type of scope you are trying to get all role"
                "assignments for.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="list_role_assignments",
        description=(
            "You can list the role assignments within a workspace, optionally filtered down"
            "to a specific scope inside of that workspace. If the scope isn't specified,"
            "the workspace will be considered the scope."
        ),
        request=GetRoleAssignmentsQueryParametersSerializer,
        responses={
            200: OpenApiRoleAssignmentSerializer(many=True),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            ObjectScopeTypeDoesNotExist: ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
        }
    )
    @validate_query_parameters(
        GetRoleAssignmentsQueryParametersSerializer, return_validated=True
    )
    def get(
        self,
        request: Request,
        workspace_id: int,
        query_params: Dict[str, Any],
    ) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        scope = query_params.get("scope", workspace)

        LicenseHandler.raise_if_user_doesnt_have_feature(RBAC, request.user, workspace)

        scope_type = object_scope_type_registry.get_by_model(scope)
        CoreHandler().check_permissions(
            request.user,
            ROLE_ASSIGNABLE_OBJECT_MAP[scope_type.type]["READ"],
            workspace=workspace,
            context=scope,
        )

        role_assignments = RoleAssignmentHandler().get_role_assignments(
            workspace, scope=scope
        )

        RoleAssignmentHandler().prefetch_role_assignment_subjects(role_assignments)
        return Response(RoleAssignmentSerializer(role_assignments, many=True).data)


class BatchRoleAssignmentsView(APIView):
    """View for assigning roles in batch"""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace in which the role assignment takes place.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="batch_assign_role",
        description=(
            "You can assign a role to a multiple subjects into the given workspace for "
            "the given scopes with this endpoint. If you want to remove the role you "
            "can omit the role property."
        ),
        request=BatchCreateRoleAssignmentSerializer,
        responses={
            200: OpenApiRoleAssignmentSerializer(many=True),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_DUPLICATE_ROLE_ASSIGNMENTS",
                    "ERROR_CANT_ASSIGN_ROLE_EXCEPTION_TO_ADMIN",
                    "ERROR_CANT_ASSIGN_ROLE_TO_SELF",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
                    "ERROR_SUBJECT_TYPE_DOES_NOT_EXIST",
                    "ERROR_ROLE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ObjectScopeTypeDoesNotExist: ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
            SubjectTypeNotExist: ERROR_SUBJECT_TYPE_DOES_NOT_EXIST,
            SubjectNotExist: ERROR_SUBJECT_DOES_NOT_EXIST,
            SubjectUnsupported: ERROR_SUBJECT_TYPE_UNSUPPORTED,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            RoleNotExist: ERROR_ROLE_DOES_NOT_EXIST,
            DuplicateRoleAssignments: ERROR_DUPLICATE_ROLE_ASSIGNMENTS,
            CannotAssignRoleToSelf: ERROR_CANT_ASSIGN_ROLE_TO_SELF,
        }
    )
    @validate_body(
        BatchCreateRoleAssignmentSerializer,
        return_validated=True,
    )
    def post(
        self,
        request: Request,
        workspace_id: int,
        data,
    ) -> Response:
        """
        Assigns or removes a role to multiple subjects on multiple scope at the same
        time.
        """

        data = data.get("items", [])
        user = request.user
        workspace = CoreHandler().get_workspace(workspace_id)

        _, duplicates = unique_dicts_in_list(
            data, unique_fields=["subject_id", "subject_type", "scope_id", "scope_type"]
        )
        if len(duplicates) > 0:
            indexes = [data.index(duplicate) for duplicate in duplicates]
            raise DuplicateRoleAssignments(indexes)

        new_role_assignments = [
            NewRoleAssignment(elt["subject"], elt["role"], elt["scope"]) for elt in data
        ]

        role_assignments = action_type_registry.get_by_type(
            BatchAssignRoleActionType
        ).do(
            user,
            new_role_assignments,
            workspace,
        )

        RoleAssignmentHandler().prefetch_role_assignment_subjects(role_assignments)
        response = [
            RoleAssignmentSerializer(ra).data if ra else None for ra in role_assignments
        ]

        return Response(response)


class EffectiveAccessView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace the scope belongs to.",
            ),
            OpenApiParameter(
                name="scope_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The id of the scope to resolve the access on.",
            ),
            OpenApiParameter(
                name="scope_type",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The type of the scope to resolve the access on.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="list_effective_access",
        description=(
            "Lists the role every user and agent of the workspace effectively holds "
            "on the given scope, and the scope it comes from: the given scope "
            "itself or one above it, held by the subject themselves or through "
            "their teams. Subjects without access to the scope are left out."
        ),
        responses={
            200: EffectiveAccessSerializer(many=True),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            ObjectScopeTypeDoesNotExist: ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
        }
    )
    @validate_query_parameters(
        GetRoleAssignmentsQueryParametersSerializer, return_validated=True
    )
    def get(
        self,
        request: Request,
        workspace_id: int,
        query_params: Dict[str, Any],
    ) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        scope = query_params["scope"]

        LicenseHandler.raise_if_user_doesnt_have_feature(RBAC, request.user, workspace)

        scope_type = object_scope_type_registry.get_by_model(scope)
        if scope_type.type not in ROLE_ASSIGNABLE_OBJECT_MAP:
            raise ScopeNotExist()
        if isinstance(scope, Workspace):
            if scope.id != workspace.id:
                raise ScopeNotExist()
        elif not scope_type.are_objects_child_of([scope], workspace)[0]:
            raise ScopeNotExist()

        CoreHandler().check_permissions(
            request.user,
            ROLE_ASSIGNABLE_OBJECT_MAP[scope_type.type]["READ"],
            workspace=workspace,
            context=scope,
        )

        effective_access = RoleAssignmentHandler().get_effective_access(
            workspace, scope
        )

        # Which teams a subject belongs to is only shown to those who may list the
        # members of the team.
        teams = {team for access in effective_access for team in access.teams}
        checks = {
            team.id: PermissionCheck(
                request.user, ListTeamSubjectsOperationType.type, team
            )
            for team in teams
        }
        results = CoreHandler().check_multiple_permissions(
            list(checks.values()), workspace=workspace
        )
        visible_team_ids = {
            team_id for team_id, check in checks.items() if results[check] is True
        }

        return Response(
            EffectiveAccessSerializer(
                effective_access,
                many=True,
                context={"visible_team_ids": visible_team_ids},
            ).data
        )


class ScopedInvitationsView(APIView):
    """Lists and creates invitations that grant a role on one scope."""

    permission_classes = (IsAuthenticated,)

    def get_throttles(self):
        throttles = super().get_throttles()

        if self.request.method == "POST":
            self.invitation_throttle = WorkspaceInvitationRateThrottle()
            throttles.append(self.invitation_throttle)

        return throttles

    def finalize_response(self, request, response, *args, **kwargs):
        # The throttle reserves a slot before this view runs, so that parallel
        # requests can't all pass the check. If no invitation was sent after all,
        # the slot is given back and the request costs the user nothing.
        if response.status_code >= 400 and hasattr(self, "invitation_throttle"):
            self.invitation_throttle.release()

        return super().finalize_response(request, response, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace the scope belongs to.",
            ),
            OpenApiParameter(
                name="scope_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The id of the scope to list the pending invitations of.",
            ),
            OpenApiParameter(
                name="scope_type",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The type of the scope to list the pending invitations of.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="list_scoped_invitations",
        description=(
            "Lists the pending invitations that grant a role on the given scope once "
            "they are accepted."
        ),
        responses={
            200: ScopedInvitationSerializer(many=True),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(
                [
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            ObjectScopeTypeDoesNotExist: ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
        }
    )
    @validate_query_parameters(
        GetRoleAssignmentsQueryParametersSerializer, return_validated=True
    )
    def get(
        self,
        request: Request,
        workspace_id: int,
        query_params: Dict[str, Any],
    ) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        scope = query_params["scope"]

        handler = RoleAssignmentHandler()
        handler.check_scoped_invitation_permissions(
            request.user, workspace, scope, operation="READ"
        )
        scoped_invitations = handler.get_scoped_invitations(workspace, scope)

        return Response(ScopedInvitationSerializer(scoped_invitations, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace the scope belongs to.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="create_scoped_invitation",
        description=(
            "Invites an email address to one scope of the workspace. The person joins "
            "the workspace without a workspace role and gets the given role on the "
            "scope once they accept. If a pending invitation already exists for the "
            "address, the scope is added to it. The invitation email is sent out "
            "immediately."
        ),
        request=CreateScopedInvitationSerializer,
        responses={
            200: ScopedInvitationSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_GROUP_USER_ALREADY_EXISTS",
                    "ERROR_CAPTCHA_VERIFICATION_FAILED",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
                    "ERROR_ROLE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ObjectScopeTypeDoesNotExist: ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            RoleNotExist: ERROR_ROLE_DOES_NOT_EXIST,
            WorkspaceUserAlreadyExists: ERROR_GROUP_USER_ALREADY_EXISTS,
            CaptchaVerificationFailed: ERROR_CAPTCHA_VERIFICATION_FAILED,
        }
    )
    @validate_body(CreateScopedInvitationSerializer, return_validated=True)
    def post(self, request: Request, workspace_id: int, data) -> Response:
        """Creates a scoped invitation and sends it to the provided email."""

        CaptchaHandler.validate_if_required(
            "workspace_invitation",
            data.get("captcha_token"),
            get_user_remote_ip_address_from_request(request),
        )

        with transaction.atomic():
            workspace = CoreHandler().get_workspace(workspace_id)
            scoped_invitation = action_type_registry.get_by_type(
                CreateScopedInvitationActionType
            ).do(
                request.user,
                workspace,
                data["email"],
                data["role"],
                data["scope"],
            )

        return Response(ScopedInvitationSerializer(scoped_invitation).data)


class ScopedInvitationView(APIView):
    """Changes or revokes the role one pending invitation grants on a scope."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scoped_invitation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The scoped invitation to change.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="update_scoped_invitation",
        description="Changes the role a pending invitation grants on its scope.",
        request=UpdateScopedInvitationSerializer,
        responses={
            200: ScopedInvitationSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(
                [
                    "ERROR_SCOPED_INVITATION_DOES_NOT_EXIST",
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_ROLE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            ScopedInvitationDoesNotExist: ERROR_SCOPED_INVITATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            RoleNotExist: ERROR_ROLE_DOES_NOT_EXIST,
        }
    )
    @validate_body(UpdateScopedInvitationSerializer, return_validated=True)
    @transaction.atomic
    def patch(self, request: Request, scoped_invitation_id: int, data) -> Response:
        scoped_invitation = RoleAssignmentHandler().get_scoped_invitation(
            scoped_invitation_id
        )
        scoped_invitation = action_type_registry.get_by_type(
            UpdateScopedInvitationActionType
        ).do(request.user, scoped_invitation, data["role"])
        return Response(ScopedInvitationSerializer(scoped_invitation).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scoped_invitation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The scoped invitation to revoke.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="delete_scoped_invitation",
        description=(
            "Revokes the role a pending invitation grants on its scope. The "
            "invitation itself and its other scopes are kept."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                ["ERROR_SCOPED_INVITATION_DOES_NOT_EXIST", "ERROR_SCOPE_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            ScopedInvitationDoesNotExist: ERROR_SCOPED_INVITATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def delete(self, request: Request, scoped_invitation_id: int) -> Response:
        scoped_invitation = RoleAssignmentHandler().get_scoped_invitation(
            scoped_invitation_id
        )
        action_type_registry.get_by_type(DeleteScopedInvitationActionType).do(
            request.user, scoped_invitation
        )
        return Response(status=204)


class ScopedInvitationLinksView(APIView):
    """Lists and creates permanent invitation links that give a role on one scope."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace the scope belongs to.",
            ),
            OpenApiParameter(
                name="scope_id",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The id of the scope to list the invitation links of.",
            ),
            OpenApiParameter(
                name="scope_type",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="The type of the scope to list the invitation links of.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="list_scoped_invitation_links",
        description=(
            "Lists the permanent invitation links that give a role on the given "
            "scope to everyone who joins through them."
        ),
        responses={
            200: ScopedInvitationLinkSerializer(many=True),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(
                [
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            ObjectScopeTypeDoesNotExist: ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
        }
    )
    @validate_query_parameters(
        GetRoleAssignmentsQueryParametersSerializer, return_validated=True
    )
    def get(
        self,
        request: Request,
        workspace_id: int,
        query_params: Dict[str, Any],
    ) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        scope = query_params["scope"]

        handler = RoleAssignmentHandler()
        handler.check_scoped_invitation_permissions(
            request.user, workspace, scope, operation="READ"
        )
        invitation_links = handler.get_scoped_invitation_links(workspace, scope)

        return Response(
            ScopedInvitationLinkSerializer(invitation_links, many=True).data
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workspace the scope belongs to.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="create_scoped_invitation_link",
        description=(
            "Creates a permanent invitation link that gives the chosen role on one "
            "scope of the workspace. People who aren't a member yet join the "
            "workspace without a workspace role. Admins of the workspace and admins "
            "of the scope can create them. Links can't be created while both new "
            "signups and signups via workspace invitations are disabled."
        ),
        request=CreateScopedInvitationLinkSerializer,
        responses={
            200: ScopedInvitationLinkSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(
                [
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_GROUP_DOES_NOT_EXIST",
                    "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST",
                    "ERROR_ROLE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ObjectScopeTypeDoesNotExist: ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            RoleNotExist: ERROR_ROLE_DOES_NOT_EXIST,
            WorkspaceInvitationLinkSignupsDisabled: (
                ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED
            ),
        }
    )
    @validate_body(CreateScopedInvitationLinkSerializer, return_validated=True)
    def post(self, request: Request, workspace_id: int, data) -> Response:
        workspace = CoreHandler().get_workspace(workspace_id)
        invitation_link = action_type_registry.get_by_type(
            CreateScopedInvitationLinkActionType
        ).do(
            request.user,
            workspace,
            data["scope"],
            data["permissions"],
            data.get("name", ""),
        )

        return Response(ScopedInvitationLinkSerializer(invitation_link).data)


class ScopedInvitationLinkView(APIView):
    """Changes or deletes one permanent invitation link to a scope."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="invitation_link_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The invitation link to change.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="update_scoped_invitation_link",
        description=(
            "Changes the name of a permanent invitation link to a scope, or the role "
            "people get on the scope when they join through it. People who already "
            "joined keep their role."
        ),
        request=UpdateScopedInvitationLinkSerializer,
        responses={
            200: ScopedInvitationLinkSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
            404: get_error_schema(
                [
                    "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST",
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                    "ERROR_ROLE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
            RoleNotExist: ERROR_ROLE_DOES_NOT_EXIST,
        }
    )
    @validate_body(UpdateScopedInvitationLinkSerializer, return_validated=True)
    def patch(self, request: Request, invitation_link_id: int, data) -> Response:
        invitation_link = RoleAssignmentHandler().get_scoped_invitation_link(
            invitation_link_id
        )
        invitation_link = action_type_registry.get_by_type(
            UpdateScopedInvitationLinkActionType
        ).do(
            request.user,
            invitation_link,
            role=data.get("permissions"),
            name=data.get("name"),
        )
        return Response(ScopedInvitationLinkSerializer(invitation_link).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="invitation_link_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The invitation link to delete.",
            ),
        ],
        tags=["Role assignments"],
        operation_id="delete_scoped_invitation_link",
        description=(
            "Deletes a permanent invitation link to a scope, after which it can't be "
            "used anymore. People who joined through it keep their role."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                [
                    "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST",
                    "ERROR_SCOPE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ScopeNotExist: ERROR_SCOPE_DOES_NOT_EXIST,
        }
    )
    def delete(self, request: Request, invitation_link_id: int) -> Response:
        invitation_link = RoleAssignmentHandler().get_scoped_invitation_link(
            invitation_link_id
        )
        action_type_registry.get_by_type(DeleteScopedInvitationLinkActionType).do(
            request.user, invitation_link
        )
        return Response(status=204)
