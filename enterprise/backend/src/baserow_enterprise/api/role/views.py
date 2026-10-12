from typing import Any, Dict
from urllib.request import Request

from django.contrib.auth import get_user_model
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from itsdangerous.exc import BadSignature
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.captcha.errors import ERROR_CAPTCHA_VERIFICATION_FAILED
from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import (
    BAD_TOKEN_SIGNATURE,
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_HOSTNAME_IS_NOT_ALLOWED,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.schemas import get_error_schema
from baserow.api.workspaces.invitations.errors import (
    ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
)
from baserow.api.workspaces.users.errors import ERROR_GROUP_USER_ALREADY_EXISTS
from baserow.core.action.registries import action_type_registry
from baserow.core.captcha.exceptions import CaptchaVerificationFailed
from baserow.core.captcha.handler import CaptchaHandler
from baserow.core.exceptions import (
    BaseURLHostnameNotAllowed,
    LastAdminOfWorkspace,
    ObjectScopeTypeDoesNotExist,
    SubjectTypeNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceInvitationDoesNotExist,
    WorkspaceUserAlreadyExists,
)
from baserow.core.handler import CoreHandler
from baserow.core.registries import object_scope_type_registry
from baserow.core.utils import (
    get_user_remote_ip_address_from_request,
    unique_dicts_in_list,
)
from baserow.throttling.handler import WorkspaceInvitationRateThrottle
from baserow_enterprise.api.errors import (
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
)
from baserow_enterprise.role.constants import ROLE_ASSIGNABLE_OBJECT_MAP
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.types import NewRoleAssignment
from baserow_premium.license.handler import LicenseHandler

from .exceptions import DuplicateRoleAssignments
from .serializers import (
    BatchCreateRoleAssignmentSerializer,
    CreateRoleAssignmentSerializer,
    CreateScopedInvitationSerializer,
    GetRoleAssignmentsQueryParametersSerializer,
    OpenApiRoleAssignmentSerializer,
    RoleAssignmentSerializer,
    ScopedInvitationSerializer,
    ScopedInvitationTargetSerializer,
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

        response = [
            RoleAssignmentSerializer(ra).data if ra else None for ra in role_assignments
        ]

        return Response(response)


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
                    "ERROR_HOSTNAME_IS_NOT_ALLOWED",
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
            BaseURLHostnameNotAllowed: ERROR_HOSTNAME_IS_NOT_ALLOWED,
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
                data["base_url"],
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
        handler = RoleAssignmentHandler()
        scoped_invitation = handler.get_scoped_invitation(scoped_invitation_id)
        scoped_invitation = handler.update_scoped_invitation(
            request.user, scoped_invitation, data["role"]
        )
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
        handler = RoleAssignmentHandler()
        scoped_invitation = handler.get_scoped_invitation(scoped_invitation_id)
        handler.delete_scoped_invitation(request.user, scoped_invitation)
        return Response(status=204)


class ScopedInvitationsByTokenView(APIView):
    """Tells where an invitation leads, for the page that welcomes the invitee."""

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="token",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The signed token of the workspace invitation.",
            )
        ],
        tags=["Role assignments"],
        operation_id="get_scoped_invitations_by_token",
        description=(
            "Lists the scopes the workspace invitation with the provided token grants "
            "a role on, with the ids needed to navigate to them. Empty for a plain "
            "workspace invitation."
        ),
        responses={
            200: ScopedInvitationTargetSerializer(many=True),
            400: get_error_schema(["BAD_TOKEN_SIGNATURE"]),
            404: get_error_schema(["ERROR_GROUP_INVITATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            BadSignature: BAD_TOKEN_SIGNATURE,
            WorkspaceInvitationDoesNotExist: ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, token: str) -> Response:
        invitation = CoreHandler().get_workspace_invitation_by_token(token)
        scoped_invitations = invitation.scoped_invitations.select_related(
            "role", "scope_type"
        )
        return Response(
            ScopedInvitationTargetSerializer(scoped_invitations, many=True).data
        )
