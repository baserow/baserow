from django.contrib.auth import get_user_model
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from loguru import logger
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK
from rest_framework.views import APIView

from baserow.api.admin.users.errors import (
    USER_ADMIN_ALREADY_EXISTS,
    USER_ADMIN_CANNOT_DEACTIVATE_SELF,
    USER_ADMIN_CANNOT_DELETE_SELF,
    USER_ADMIN_UNKNOWN_USER,
)
from baserow.api.admin.users.serializers import (
    UserAdminCreateSerializer,
    UserAdminResponseSerializer,
    UserAdminUpdateSerializer,
)
from baserow.api.admin.views import AdminListingView
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.api.user.registries import member_data_registry
from baserow.api.user.schemas import authenticate_user_schema
from baserow.api.user.serializers import get_all_user_data_serialized
from baserow.core.admin.users.exceptions import (
    CannotDeactivateYourselfException,
    CannotDeleteYourselfException,
    UserDoesNotExistException,
)
from baserow.core.admin.users.handler import UserAdminHandler
from baserow.core.user.exceptions import DeactivatedUserException, UserAlreadyExist
from baserow.core.user.utils import generate_session_tokens_for_user

from .serializers import BaserowImpersonateAuthTokenSerializer

User = get_user_model()


class UsersAdminView(AdminListingView):
    serializer_class = UserAdminResponseSerializer
    search_fields = ["id", "username", "first_name"]
    sort_field_mapping = {
        "id": "id",
        "is_active": "is_active",
        "name": "first_name",
        "username": "username",
        "date_joined": "date_joined",
        "last_login": "last_login",
    }

    def get_queryset(self, request):
        return User.objects.prefetch_related(
            "workspaceuser_set", "workspaceuser_set__workspace"
        ).all()

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_list_users",
        description="Returns all users with detailed information on each user, "
        "if the requesting user is staff.",
        **AdminListingView.get_extend_schema_parameters(
            "users", serializer_class, search_fields, sort_field_mapping
        ),
    )
    def get(self, request):
        response = super().get(request)
        results = response.data["results"]
        user_ids = [result["id"] for result in results]
        # Iterate over any registered `member_data_registry member data types and
        # annotate the response with it.
        for data_type in member_data_registry.get_all():
            data_type.annotate_serialized_admin_users_data(
                user_ids, results, request.user
            )
        return response

    @extend_schema(
        tags=["Admin"],
        request=UserAdminCreateSerializer,
        operation_id="admin_create_user",
        description=(
            "Creates and returns a new user if the requesting user is staff. This "
            "works even if new signups are disabled."
        ),
        responses={
            200: UserAdminResponseSerializer(),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_FEATURE_NOT_AVAILABLE",
                    "USER_ADMIN_ALREADY_EXISTS",
                ]
            ),
        },
    )
    @validate_body(UserAdminCreateSerializer)
    @map_exceptions(
        {
            UserAlreadyExist: USER_ADMIN_ALREADY_EXISTS,
            DeactivatedUserException: USER_ADMIN_ALREADY_EXISTS,
        }
    )
    @transaction.atomic
    def post(self, request, data) -> Response:
        """Creates a new user with the supplied attributes."""

        handler = UserAdminHandler()
        user = handler.create_user(request.user, **data)

        return Response(UserAdminResponseSerializer(user).data)


class UserAdminView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        request=UserAdminUpdateSerializer,
        operation_id="admin_edit_user",
        description=f"Updates specified user attributes and returns the updated user if"
        f" the requesting user is staff. You cannot update yourself to no longer be an "
        f"admin or active.",
        parameters=[
            OpenApiParameter(
                name="user_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the user to edit",
            ),
        ],
        responses={
            200: UserAdminResponseSerializer(),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "USER_ADMIN_CANNOT_DEACTIVATE_SELF",
                    "USER_ADMIN_UNKNOWN_USER",
                    "USER_ADMIN_ALREADY_EXISTS",
                    "ERROR_FEATURE_NOT_AVAILABLE",
                ]
            ),
            401: None,
        },
    )
    @validate_body(UserAdminUpdateSerializer, partial=True)
    @map_exceptions(
        {
            CannotDeactivateYourselfException: USER_ADMIN_CANNOT_DEACTIVATE_SELF,
            UserDoesNotExistException: USER_ADMIN_UNKNOWN_USER,
            UserAlreadyExist: USER_ADMIN_ALREADY_EXISTS,
        }
    )
    @transaction.atomic
    def patch(self, request, user_id, data):
        """
        Updates the specified user with the supplied attributes. Will raise an exception
        if you attempt un-staff or de-activate yourself.
        """

        user_id = int(user_id)

        handler = UserAdminHandler()
        user = handler.update_user(request.user, user_id, **data)

        return Response(UserAdminResponseSerializer(user).data)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_delete_user",
        description="Deletes the specified user, if the requesting user has admin "
        "permissions. You cannot delete yourself.",
        parameters=[
            OpenApiParameter(
                name="user_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the user to delete",
            ),
        ],
        responses={
            200: None,
            400: get_error_schema(
                [
                    "USER_ADMIN_CANNOT_DELETE_SELF",
                    "USER_ADMIN_UNKNOWN_USER",
                    "ERROR_FEATURE_NOT_AVAILABLE",
                ]
            ),
            401: None,
        },
    )
    @map_exceptions(
        {
            CannotDeleteYourselfException: USER_ADMIN_CANNOT_DELETE_SELF,
            UserDoesNotExistException: USER_ADMIN_UNKNOWN_USER,
        }
    )
    @transaction.atomic
    def delete(self, request, user_id):
        """
        Deletes the specified user. Raises an exception if you attempt to delete
        yourself.
        """

        user_id = int(user_id)

        handler = UserAdminHandler()
        handler.delete_user(request.user, user_id)

        return Response(status=204)


class UserAdminImpersonateView(GenericAPIView):
    """
    Impersonate the user by retrieving its JWT.

    Returns:
        dict: {
            "access_token": user's JWT token,
            "refresh_refresh": user's JWT refresh token
        }
    """

    permission_classes = (IsAdminUser,)
    serializer_class = BaserowImpersonateAuthTokenSerializer

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_impersonate_user",
        description=(
            "This endpoint allows staff to impersonate another user by requesting a "
            "JWT token and user object. The requesting user must have staff access in "
            "order to do this. It's not possible to impersonate a superuser or staff."
        ),
        request=BaserowImpersonateAuthTokenSerializer,
        responses={
            200: authenticate_user_schema,
        },
    )
    @map_exceptions(
        {
            CannotDeleteYourselfException: USER_ADMIN_CANNOT_DELETE_SELF,
            UserDoesNotExistException: USER_ADMIN_UNKNOWN_USER,
        }
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        logger.info(
            f"{request.user.username} ({request.user.id}) requested an "
            f"impersonate token for {user.username} ({user.id})."
        )

        serialized_data = {
            **generate_session_tokens_for_user(user, include_refresh_token=True),
            **get_all_user_data_serialized(user, request),
        }

        return Response(serialized_data, status=HTTP_200_OK)
