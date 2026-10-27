from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_USER_INVALID_GROUP_PERMISSIONS,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.schemas import get_error_schema
from baserow.api.workspaces.serializers import WorkspaceUserWorkspaceSerializer
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import (
    CreateWorkspaceInvitationLinkActionType,
    DeleteWorkspaceInvitationLinkActionType,
    JoinWorkspaceViaInvitationLinkActionType,
    UpdateWorkspaceInvitationLinkActionType,
)
from baserow.core.exceptions import (
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceInvitationLinkDoesNotExist,
    WorkspaceInvitationLinkSignupsDisabled,
)
from baserow.core.handler import CoreHandler

from .errors import (
    ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST,
    ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED,
)
from .serializers import (
    CreateWorkspaceInvitationLinkSerializer,
    PublicWorkspaceInvitationLinkSerializer,
    UpdateWorkspaceInvitationLinkSerializer,
    WorkspaceInvitationLinkSerializer,
)


class WorkspaceInvitationLinksView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the invitation links of the workspace "
                "related to the provided value.",
            )
        ],
        tags=["Workspace invitation links"],
        operation_id="list_workspace_invitation_links",
        description=(
            "Lists all the invitation links of the workspace related to the provided "
            "`workspace_id` parameter if the authorized user has admin rights to that "
            "workspace."
        ),
        responses={
            200: WorkspaceInvitationLinkSerializer(many=True),
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
    def get(self, request, workspace_id):
        """Lists all the invitation links of the provided workspace id."""

        workspace = CoreHandler().get_workspace(workspace_id)
        invitation_links = CoreHandler().list_workspace_invitation_links(
            request.user, workspace
        )

        serializer = WorkspaceInvitationLinkSerializer(invitation_links, many=True)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workspace_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates an invitation link to the workspace related to "
                "the provided value.",
            )
        ],
        tags=["Workspace invitation links"],
        operation_id="create_workspace_invitation_link",
        description=(
            "Creates a new permanent invitation link if the authorized user has admin "
            "rights to the related workspace. Anyone with the link can join the "
            "workspace with the permissions of the link until the link is deleted. "
            "Links can't be created while both new signups and signups via workspace "
            "invitations are disabled."
        ),
        request=CreateWorkspaceInvitationLinkSerializer,
        responses={
            200: WorkspaceInvitationLinkSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(CreateWorkspaceInvitationLinkSerializer)
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
            WorkspaceInvitationLinkSignupsDisabled: (
                ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED
            ),
        }
    )
    def post(self, request, data, workspace_id):
        """Creates a new invitation link for the provided workspace id."""

        workspace = CoreHandler().get_workspace(workspace_id)
        invitation_link = action_type_registry.get(
            CreateWorkspaceInvitationLinkActionType.type
        ).do(request.user, workspace, data["permissions"])

        return Response(WorkspaceInvitationLinkSerializer(invitation_link).data)


class WorkspaceInvitationLinkView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="invitation_link_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the invitation link related to the provided "
                "value.",
            )
        ],
        tags=["Workspace invitation links"],
        operation_id="update_workspace_invitation_link",
        description=(
            "Updates the permissions people get when joining through the invitation "
            "link if the authorized user has admin rights to the related workspace. "
            "People who already joined keep their permissions."
        ),
        request=UpdateWorkspaceInvitationLinkSerializer,
        responses={
            200: WorkspaceInvitationLinkSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(UpdateWorkspaceInvitationLinkSerializer)
    @map_exceptions(
        {
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def patch(self, request, data, invitation_link_id):
        """Updates the permissions of an invitation link."""

        invitation_link = CoreHandler().get_workspace_invitation_link(
            invitation_link_id
        )
        invitation_link = action_type_registry.get(
            UpdateWorkspaceInvitationLinkActionType.type
        ).do(request.user, invitation_link, data["permissions"])

        return Response(WorkspaceInvitationLinkSerializer(invitation_link).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="invitation_link_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the invitation link related to the provided "
                "value.",
            )
        ],
        tags=["Workspace invitation links"],
        operation_id="delete_workspace_invitation_link",
        description=(
            "Deletes an invitation link if the authorized user has admin rights to "
            "the related workspace. The link can't be used anymore afterwards."
        ),
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_USER_INVALID_GROUP_PERMISSIONS"]
            ),
            404: get_error_schema(["ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
        }
    )
    def delete(self, request, invitation_link_id):
        """Deletes an invitation link."""

        invitation_link = CoreHandler().get_workspace_invitation_link(
            invitation_link_id
        )
        action_type_registry.get(DeleteWorkspaceInvitationLinkActionType.type).do(
            request.user, invitation_link
        )

        return Response(status=204)


class PublicWorkspaceInvitationLinkView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Returns the invitation link related to the provided slug.",
            )
        ],
        tags=["Workspace invitation links"],
        operation_id="get_public_workspace_invitation_link",
        description=(
            "Responds with the workspace and the inviter of the invitation link with "
            "the provided slug, so that someone who opens the link knows what they "
            "join."
        ),
        responses={
            200: PublicWorkspaceInvitationLinkSerializer,
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
        }
    )
    def get(self, request, slug):
        """Responds with the public details of the invitation link."""

        invitation_link = CoreHandler().get_workspace_invitation_link_by_slug(slug)
        return Response(PublicWorkspaceInvitationLinkSerializer(invitation_link).data)


class JoinWorkspaceInvitationLinkView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Joins the workspace of the invitation link related to "
                "the provided slug.",
            )
        ],
        tags=["Workspace invitation links"],
        operation_id="join_workspace_invitation_link",
        description=(
            "Adds the authorized user to the workspace of the invitation link with "
            "the permissions of the link. Someone who is already a member keeps "
            "their current permissions."
        ),
        request=None,
        responses={
            200: WorkspaceUserWorkspaceSerializer,
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
        }
    )
    def post(self, request, slug):
        """Joins the workspace of the invitation link."""

        invitation_link = CoreHandler().get_workspace_invitation_link_by_slug(slug)
        workspace_user = action_type_registry.get(
            JoinWorkspaceViaInvitationLinkActionType.type
        ).do(request.user, invitation_link)
        workspaceuser_workspace = (
            CoreHandler()
            .get_workspaceuser_workspace_queryset()
            .get(id=workspace_user.id)
        )
        return Response(WorkspaceUserWorkspaceSerializer(workspaceuser_workspace).data)
