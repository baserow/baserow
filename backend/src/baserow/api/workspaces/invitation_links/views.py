from typing import Optional

from django.conf import settings
from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_USER_INVALID_GROUP_PERMISSIONS,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.schemas import get_error_schema
from baserow.api.workspaces.errors import ERROR_INVALID_WORKSPACE_ROLE
from baserow.api.workspaces.serializers import WorkspaceUserWorkspaceSerializer
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import (
    CreateWorkspaceInvitationLinkActionType,
    DeleteWorkspaceInvitationLinkActionType,
    JoinWorkspaceViaInvitationLinkActionType,
    UpdateWorkspaceInvitationLinkActionType,
)
from baserow.core.exceptions import (
    InvalidWorkspaceRole,
    UserInvalidWorkspacePermissionsError,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceInvitationLinkDoesNotExist,
    WorkspaceInvitationLinkPasswordRequired,
    WorkspaceInvitationLinkSignupsDisabled,
)
from baserow.core.handler import CoreHandler

from .errors import (
    ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST,
    ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED,
    ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED,
)
from .serializers import (
    CreateWorkspaceInvitationLinkSerializer,
    InvitationLinkAuthRequestSerializer,
    InvitationLinkAuthResponseSerializer,
    PublicWorkspaceInvitationLinkSerializer,
    UpdateWorkspaceInvitationLinkSerializer,
    WorkspaceInvitationLinkSerializer,
)


def get_invitation_link_authorization_token(request: Request) -> Optional[str]:
    """
    Returns the token that grants access to a password protected invitation link,
    if the request carries one in the `INVITATION_LINK_AUTHORIZATION_HEADER`.
    """

    auth_header = request.headers.get(settings.INVITATION_LINK_AUTHORIZATION_HEADER)
    try:
        _, token = auth_header.split(" ", 1)
    except (AttributeError, ValueError):
        return None
    return token


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
                    "ERROR_INVALID_WORKSPACE_ROLE",
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
            InvalidWorkspaceRole: ERROR_INVALID_WORKSPACE_ROLE,
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
        ).do(request.user, workspace, data["permissions"], data.get("name", ""))

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
            "Updates the name of the invitation link, the permissions people get "
            "when joining through it or its password if the authorized user has "
            "admin rights to the related workspace. People who already joined keep "
            "their permissions. Changing the password invalidates the access tokens "
            "handed out for the previous one."
        ),
        request=UpdateWorkspaceInvitationLinkSerializer,
        responses={
            200: WorkspaceInvitationLinkSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_USER_INVALID_GROUP_PERMISSIONS",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_INVALID_WORKSPACE_ROLE",
                ]
            ),
            404: get_error_schema(["ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body(
        UpdateWorkspaceInvitationLinkSerializer, partial=True, return_validated=True
    )
    @map_exceptions(
        {
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            UserInvalidWorkspacePermissionsError: ERROR_USER_INVALID_GROUP_PERMISSIONS,
            InvalidWorkspaceRole: ERROR_INVALID_WORKSPACE_ROLE,
        }
    )
    def patch(self, request, data, invitation_link_id):
        """Updates the name or the permissions of an invitation link."""

        invitation_link = CoreHandler().get_workspace_invitation_link(
            invitation_link_id
        )
        invitation_link = action_type_registry.get(
            UpdateWorkspaceInvitationLinkActionType.type
        ).do(request.user, invitation_link, **data)

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
            "join. For a member whose role the link would raise, it also responds "
            "with their current role and the role of the link. A password protected "
            "link requires the token of the auth endpoint in the "
            "`Baserow-Invitation-Link-Authorization` header."
        ),
        responses={
            200: PublicWorkspaceInvitationLinkSerializer,
            401: get_error_schema(
                ["ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED"]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            WorkspaceInvitationLinkPasswordRequired: (
                ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED
            ),
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
        }
    )
    def get(self, request, slug):
        """Responds with the public details of the invitation link."""

        invitation_link = CoreHandler().get_workspace_invitation_link_by_slug(
            slug, access_token=get_invitation_link_authorization_token(request)
        )
        return Response(
            PublicWorkspaceInvitationLinkSerializer(
                invitation_link, context={"user": request.user}
            ).data
        )


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
            "the permissions of the link. Someone who is already a member gets the "
            "permissions of the link when they are higher than their own, and "
            "otherwise keeps their current permissions."
        ),
        request=None,
        responses={
            200: WorkspaceUserWorkspaceSerializer,
            401: get_error_schema(
                ["ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED"]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceInvitationLinkPasswordRequired: (
                ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED
            ),
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
        }
    )
    def post(self, request, slug):
        """Joins the workspace of the invitation link."""

        invitation_link = CoreHandler().get_workspace_invitation_link_by_slug(
            slug, access_token=get_invitation_link_authorization_token(request)
        )
        workspace_user = action_type_registry.get(
            JoinWorkspaceViaInvitationLinkActionType.type
        ).do(request.user, invitation_link)
        workspaceuser_workspace = (
            CoreHandler()
            .get_workspaceuser_workspace_queryset()
            .get(id=workspace_user.id)
        )
        return Response(WorkspaceUserWorkspaceSerializer(workspaceuser_workspace).data)


class InvitationLinkAuthView(APIView):
    """
    Exchanges the password of a password protected invitation link for a
    non-expiring token that the other public link endpoints require.
    """

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The slug of the password protected invitation link.",
            )
        ],
        tags=["Workspace invitation links"],
        operation_id="workspace_invitation_link_token_auth",
        description=(
            "Returns a never-expiring token for the password protected invitation "
            "link if the password matches the one set by the admins. The token "
            "must be sent in the `Baserow-Invitation-Link-Authorization` header, as "
            "`JWT <token>`, to see or join the link, and as "
            "`workspace_invitation_link_token` to sign up through it."
        ),
        request=InvitationLinkAuthRequestSerializer,
        responses={
            200: InvitationLinkAuthResponseSerializer,
            401: {"description": "The password provided for this link is incorrect"},
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(InvitationLinkAuthRequestSerializer)
    @map_exceptions(
        {
            WorkspaceInvitationLinkDoesNotExist: (
                ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST
            ),
        }
    )
    def post(self, request, data, slug):
        handler = CoreHandler()
        invitation_link = handler.get_workspace_invitation_link_by_slug(
            slug, check_password=False
        )

        if not invitation_link.has_password or not invitation_link.check_password(
            data["password"]
        ):
            raise AuthenticationFailed()

        return Response(
            InvitationLinkAuthResponseSerializer(
                {
                    "access_token": handler.encode_invitation_link_access_token(
                        invitation_link
                    )
                }
            ).data
        )
