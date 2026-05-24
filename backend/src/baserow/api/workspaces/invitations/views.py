from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from itsdangerous.exc import BadSignature
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import (
    BAD_TOKEN_SIGNATURE,
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_HOSTNAME_IS_NOT_ALLOWED,
    ERROR_USER_INVALID_GROUP_PERMISSIONS,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.mixins import SearchableViewMixin, SortableViewMixin
from baserow.api.schemas import get_error_schema
from baserow.api.workspaces.invitations.errors import (
    ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
    ERROR_GROUP_INVITATION_EMAIL_MISMATCH,
)
from baserow.api.workspaces.serializers import WorkspaceUserWorkspaceSerializer
from baserow.api.workspaces.users.errors import ERROR_GROUP_USER_ALREADY_EXISTS
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import (
    AcceptWorkspaceInvitationActionType,
    CreateWorkspaceInvitationActionType,
    DeleteWorkspaceInvitationActionType,
    RejectWorkspaceInvitationActionType,
    UpdateWorkspaceInvitationActionType,
)
from baserow.core.exceptions import (
    BaseURLHostnameNotAllowed,
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceInvitationDoesNotExist,
    WorkspaceInvitationEmailMismatch,
    WorkspaceUserAlreadyExists,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import WorkspaceInvitation
from baserow.core.operations import (
    ListInvitationsWorkspaceOperationType,
    ReadInvitationWorkspaceOperationType,
)

from .serializers import (
    CreateWorkspaceInvitationSerializer,
    GetWorkspaceInvitationsViewQuerySerializer,
    UpdateWorkspaceInvitationSerializer,
    UserWorkspaceInvitationSerializer,
    WorkspaceInvitationSerializer,
)

User = get_user_model()


class WorkspaceInvitationsView(APIView, SortableViewMixin, SearchableViewMixin):
    permission_classes = (IsAuthenticated,)
    search_fields = ["email"]
    sort_field_mapping = {
        "email": "email",
    }

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only invitations that are in the workspace related "
                "to the provided value.",
            )
        ],
        tags=["Workspace invitations"],
        operation_id="list_workspace_invitations",
        description=(
            "Lists all the workspace invitations of the workspace related to the provided "
            "`workspace_id` parameter if the authorized user has admin rights to that "
            "workspace."
        ),
        responses={
            200: WorkspaceInvitationSerializer(many=True),
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_USER_INVALID_GROUP_PERMISSIONS"]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    @validate_query_parameters(GetWorkspaceInvitationsViewQuerySerializer)
    def get(self, request, workspace_id, query_params):
        """Lists all the invitations of the provided workspace id."""

        search = query_params.get("search")
        sorts = query_params.get("sorts")

        workspace = CoreHandler().get_workspace(workspace_id)

        CoreHandler().check_permissions(
            request.user,
            ListInvitationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        workspace_invitations = WorkspaceInvitation.objects.filter(workspace=workspace)

        workspace_invitations = self.apply_search(search, workspace_invitations)
        workspace_invitations = self.apply_sorts_or_default_sort(
            sorts, workspace_invitations
        )

        serializer = WorkspaceInvitationSerializer(workspace_invitations, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a workspace invitation to the workspace related to the "
                "provided value.",
            )
        ],
        tags=["Workspace invitations"],
        operation_id="create_workspace_invitation",
        description=(
            "Creates a new workspace invitations for an email address if the authorized "
            "user has admin rights to the related workspace. An email containing a sign "
            "up link will be send to the user."
        ),
        request=CreateWorkspaceInvitationSerializer,
        responses={
            200: WorkspaceInvitationSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(CreateWorkspaceInvitationSerializer)
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
            WorkspaceUserAlreadyExists: ERROR_GROUP_USER_ALREADY_EXISTS,
            BaseURLHostnameNotAllowed: ERROR_HOSTNAME_IS_NOT_ALLOWED,
        }
    )
    def post(self, request, data, workspace_id):
        """Creates a new workspace invitation and sends it the provided email."""

        workspace = CoreHandler().get_workspace(workspace_id)
        workspace_invitation = action_type_registry.get(
            CreateWorkspaceInvitationActionType.type
        ).do(
            request.user,
            workspace,
            data["email"],
            data["permissions"],
            data["base_url"],
        )

        return Response(WorkspaceInvitationSerializer(workspace_invitation).data)


class WorkspaceInvitationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_invitation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the workspace invitation related to the provided "
                "value.",
            )
        ],
        tags=["Workspace invitations"],
        operation_id="get_workspace_invitation",
        description=(
            "Returns the requested workspace invitation if the authorized user has admin "
            "right to the related workspace"
        ),
        responses={
            200: WorkspaceInvitationSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_USER_INVALID_GROUP_PERMISSIONS"]
            ),
            404: get_error_schema(["ERROR_GROUP_INVITATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceInvitationDoesNotExist: ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def get(self, request, workspace_invitation_id):
        """
        Selects a single workspace invitation and responds with a serialized version.
        """

        workspace_invitation = CoreHandler().get_workspace_invitation(
            workspace_invitation_id
        )

        CoreHandler().check_permissions(
            request.user,
            ReadInvitationWorkspaceOperationType.type,
            workspace=workspace_invitation.workspace,
            context=workspace_invitation,
        )

        return Response(WorkspaceInvitationSerializer(workspace_invitation).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_invitation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the workspace invitation related to the provided "
                "value.",
            )
        ],
        tags=["Workspace invitations"],
        operation_id="update_workspace_invitation",
        description=(
            "Updates the existing workspace invitation related to the provided "
            "`workspace_invitation_id` param if the authorized user has admin rights to "
            "the related workspace."
        ),
        request=UpdateWorkspaceInvitationSerializer,
        responses={
            200: WorkspaceInvitationSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_INVITATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateWorkspaceInvitationSerializer)
    @map_exceptions(
        {
            WorkspaceInvitationDoesNotExist: ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def patch(self, request, data, workspace_invitation_id):
        """Updates the workspace invitation if the user belongs to the workspace."""

        workspace_invitation = CoreHandler().get_workspace_invitation(
            workspace_invitation_id,
            base_queryset=WorkspaceInvitation.objects.select_for_update(of=("self",)),
        )
        workspace_invitation = action_type_registry.get(
            UpdateWorkspaceInvitationActionType.type
        ).do(request.user, workspace_invitation, **data)
        return Response(WorkspaceInvitationSerializer(workspace_invitation).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_invitation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the workspace invitation related to the provided "
                "value.",
            )
        ],
        tags=["Workspace invitations"],
        operation_id="delete_workspace_invitation",
        description=(
            "Deletes a workspace invitation if the authorized user has admin rights to "
            "the related workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_USER_INVALID_GROUP_PERMISSIONS"]
            ),
            404: get_error_schema(["ERROR_GROUP_INVITATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceInvitationDoesNotExist: ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def delete(self, request, workspace_invitation_id):
        """
        Deletes an existing workspace_invitation if the user belongs to the workspace.
        """

        workspace_invitation = CoreHandler().get_workspace_invitation(
            workspace_invitation_id,
            base_queryset=WorkspaceInvitation.objects.select_for_update(of=("self",)),
        )
        action_type_registry.get(DeleteWorkspaceInvitationActionType.type).do(
            request.user, workspace_invitation
        )
        return Response(status=204)


class AcceptWorkspaceInvitationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_invitation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Accepts the workspace invitation related to the provided "
                "value.",
            )
        ],
        tags=["Workspace invitations"],
        operation_id="accept_workspace_invitation",
        description=(
            "Accepts a workspace invitation with the given id if the email address of the "
            "user matches that of the invitation."
        ),
        request=None,
        responses={
            200: WorkspaceUserWorkspaceSerializer,
            400: get_error_schema(["ERROR_GROUP_INVITATION_EMAIL_MISMATCH"]),
            404: get_error_schema(["ERROR_GROUP_INVITATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceInvitationEmailMismatch: ERROR_GROUP_INVITATION_EMAIL_MISMATCH,
            WorkspaceInvitationDoesNotExist: ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
        }
    )
    def post(self, request, workspace_invitation_id):
        """Accepts a workspace invitation."""

        try:
            workspace_invitation = WorkspaceInvitation.objects.select_related(
                "workspace"
            ).get(id=workspace_invitation_id)
        except WorkspaceInvitation.DoesNotExist:
            raise WorkspaceInvitationDoesNotExist(
                f"The workspace invitation with id {workspace_invitation_id} does not exist."
            )

        workspace_user = action_type_registry.get(
            AcceptWorkspaceInvitationActionType.type
        ).do(request.user, workspace_invitation)
        workspaceuser_workspace = (
            CoreHandler()
            .get_workspaceuser_workspace_queryset()
            .get(id=workspace_user.id)
        )
        return Response(WorkspaceUserWorkspaceSerializer(workspaceuser_workspace).data)


class RejectWorkspaceInvitationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_invitation_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Rejects the workspace invitation related to the provided "
                "value.",
            )
        ],
        tags=["Workspace invitations"],
        operation_id="reject_workspace_invitation",
        description=(
            "Rejects a workspace invitation with the given id if the email address of the "
            "user matches that of the invitation."
        ),
        request=None,
        responses={
            204: None,
            400: get_error_schema(["ERROR_GROUP_INVITATION_EMAIL_MISMATCH"]),
            404: get_error_schema(["ERROR_GROUP_INVITATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceInvitationEmailMismatch: ERROR_GROUP_INVITATION_EMAIL_MISMATCH,
            WorkspaceInvitationDoesNotExist: ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
        }
    )
    def post(self, request, workspace_invitation_id):
        """Rejects a workspace invitation."""

        try:
            workspace_invitation = WorkspaceInvitation.objects.select_related(
                "workspace"
            ).get(id=workspace_invitation_id)
        except WorkspaceInvitation.DoesNotExist:
            raise WorkspaceInvitationDoesNotExist(
                f"The workspace invitation with id {workspace_invitation_id} does not exist."
            )

        action_type_registry.get(RejectWorkspaceInvitationActionType.type).do(
            request.user, workspace_invitation
        )
        return Response(status=204)


class WorkspaceInvitationByTokenView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="token",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Returns the workspace invitation related to the provided "
                "token.",
            )
        ],
        tags=["Workspace invitations"],
        operation_id="get_workspace_invitation_by_token",
        description=(
            "Responds with the serialized workspace invitation if an invitation with the "
            "provided token is found."
        ),
        responses={
            200: UserWorkspaceInvitationSerializer,
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
    def get(self, request, token):
        """
        Responds with the serialized workspace invitation if an invitation with the
        provided token is found.
        """

        exists_queryset = User.objects.filter(username=OuterRef("email"))
        workspace_invitation = CoreHandler().get_workspace_invitation_by_token(
            token,
            base_queryset=WorkspaceInvitation.objects.annotate(
                email_exists=Exists(exists_queryset)
            ),
        )
        return Response(UserWorkspaceInvitationSerializer(workspace_invitation).data)
