from types import SimpleNamespace
from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from baserow.api.applications.errors import (
    ERROR_APPLICATION_DOES_NOT_EXIST,
    ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
)
from baserow.api.authentication import JSONWebTokenAuthentication
from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_body_custom_fields,
)
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.user.errors import (
    ERROR_INVALID_CREDENTIALS,
    ERROR_INVALID_REFRESH_TOKEN,
    ERROR_REFRESH_TOKEN_ALREADY_BLACKLISTED,
)
from baserow.api.user.views import BlacklistJSONWebToken
from baserow.api.user_sources.errors import (
    ERROR_AUTH_PROVIDER_CANT_BE_CREATED,
    ERROR_AUTH_PROVIDER_TYPE_DOES_NOT_EXIST,
    ERROR_AUTH_PROVIDER_TYPE_NOT_COMPATIBLE,
    ERROR_USER_SOURCE_DOES_NOT_EXIST,
    ERROR_USER_SOURCE_IMPROPERLY_CONFIGURED,
    ERROR_USER_SOURCE_NOT_IN_SAME_APPLICATION,
)
from baserow.api.user_sources.schemas import authenticate_schema, refresh_schema
from baserow.api.user_sources.serializers import (
    CreateUserSourceSerializer,
    MoveUserSourceSerializer,
    TokenRefreshSerializer,
    UpdateUserSourceSerializer,
    UserSourceForceTokenObtainSerializer,
    UserSourceRolesSerializer,
    UserSourceSerializer,
    UserSourceTokenObtainSerializer,
    UsersPerUserSourceSerializer,
)
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    type_from_data_or_registry,
    validate_data_custom_fields,
)
from baserow.core.app_auth_providers.exceptions import (
    AppAuthenticationProviderTypeDoesNotExist,
    IncompatibleUserSourceType,
)
from baserow.core.auth_provider.exceptions import CannotCreateAuthProvider
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationOperationNotSupported,
)
from baserow.core.handler import CoreHandler
from baserow.core.user.exceptions import RefreshTokenAlreadyBlacklisted
from baserow.core.user_sources.exceptions import (
    UserSourceDoesNotExist,
    UserSourceImproperlyConfigured,
    UserSourceNotInSameApplication,
)
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.jwt_token import UserSourceToken
from baserow.core.user_sources.registries import user_source_type_registry
from baserow.core.user_sources.service import UserSourceService


class UserSourcesView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the user_sources of the application related "
                "to the provided Id.",
            )
        ],
        tags=["User sources"],
        operation_id="list_application_user_sources",
        description=(
            "Lists all the user_sources of the application related to the provided "
            "parameter if the user has access to the related application's workspace. "
            "If the workspace is related to a template, then this endpoint will be "
            "publicly accessible."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                user_source_type_registry, UserSourceSerializer, many=True
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, application_id):
        """
        Responds with a list of serialized user_sources that belong to the application
        if the user has access to that application.
        """

        application = CoreHandler().get_application(application_id)

        user_sources = UserSourceService().get_user_sources(request.user, application)

        data = [
            user_source_type_registry.get_serializer(
                user_source,
                UserSourceSerializer,
            ).data
            for user_source in user_sources
        ]

        return Response(data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates an user_source for the application related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["User sources"],
        operation_id="create_application_user_source",
        description="Creates a new user_source",
        request=DiscriminatorCustomFieldsMappingSerializer(
            user_source_type_registry,
            CreateUserSourceSerializer,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                user_source_type_registry, UserSourceSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            ApplicationOperationNotSupported: ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
            IncompatibleUserSourceType: ERROR_AUTH_PROVIDER_TYPE_NOT_COMPATIBLE,
            CannotCreateAuthProvider: ERROR_AUTH_PROVIDER_CANT_BE_CREATED,
            AppAuthenticationProviderTypeDoesNotExist: ERROR_AUTH_PROVIDER_TYPE_DOES_NOT_EXIST,
        }
    )
    @validate_body_custom_fields(
        user_source_type_registry,
        base_serializer_class=CreateUserSourceSerializer,
    )
    def post(self, request, data: Dict, application_id: int):
        """Creates a new user_source."""

        type_name = data.pop("type")
        application = CoreHandler().get_application(application_id)

        before_id = data.pop("before_id", None)
        before = UserSourceHandler().get_user_source(before_id) if before_id else None

        user_source_type = user_source_type_registry.get(type_name)
        user_source = UserSourceService().create_user_source(
            request.user, user_source_type, application, before=before, **data
        )

        serializer = user_source_type_registry.get_serializer(
            user_source,
            UserSourceSerializer,
        )

        return Response(serializer.data)


class UserSourceRolesView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the roles of the application related "
                "to the provided Id.",
            )
        ],
        tags=["User source roles"],
        operation_id="list_application_user_source_roles",
        description=(
            "Lists all the roles of the application related to the provided "
            "parameter if the user has access to the related application's workspace. "
            "If the workspace is related to a template, then this endpoint will be "
            "publicly accessible."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                user_source_type_registry, UserSourceRolesSerializer
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, application_id):
        """
        Responds with a list of roles that belong to the application
        if the user has access to that application.
        """

        application = CoreHandler().get_application(application_id)

        user_sources = UserSourceService().get_user_sources(request.user, application)

        data = [
            UserSourceRolesSerializer(user_source).data for user_source in user_sources
        ]

        return Response(data)


class UserSourceView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the user_source",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["User sources"],
        operation_id="update_application_user_source",
        description="Updates an existing user_source.",
        request=CustomFieldRegistryMappingSerializer(
            user_source_type_registry,
            UpdateUserSourceSerializer,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                user_source_type_registry, UserSourceSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_USER_SOURCE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
            IncompatibleUserSourceType: ERROR_AUTH_PROVIDER_TYPE_NOT_COMPATIBLE,
            CannotCreateAuthProvider: ERROR_AUTH_PROVIDER_CANT_BE_CREATED,
            AppAuthenticationProviderTypeDoesNotExist: ERROR_AUTH_PROVIDER_TYPE_DOES_NOT_EXIST,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, user_source_id: int):
        """
        Update a user_source.
        """

        user_source = UserSourceHandler().get_user_source_for_update(user_source_id)
        user_source_type = type_from_data_or_registry(
            request.data, user_source_type_registry, user_source
        )

        data = validate_data_custom_fields(
            user_source_type.type,
            user_source_type_registry,
            request.data,
            base_serializer_class=UpdateUserSourceSerializer,
            return_validated=True,
        )

        user_source_updated = UserSourceService().update_user_source(
            request.user, user_source, **data
        )

        serializer = user_source_type_registry.get_serializer(
            user_source_updated,
            UserSourceSerializer,
        )

        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the user_source",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["User sources"],
        operation_id="delete_application_user_source",
        description="Deletes the user_source related by the given id.",
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_USER_SOURCE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def delete(self, request, user_source_id: int):
        """
        Deletes an user_source.
        """

        user_source = UserSourceHandler().get_user_source_for_update(user_source_id)

        UserSourceService().delete_user_source(request.user, user_source)

        return Response(status=204)


class MoveUserSourceView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the user_source to move",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["User sources"],
        operation_id="move_application_user_source",
        description=(
            "Moves the user_source in the application before another user_source or at "
            "the end of the application if no before user_source is given. "
            "The user_sources must belong to the same application."
        ),
        request=MoveUserSourceSerializer,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                user_source_type_registry, UserSourceSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_SOURCE_NOT_IN_SAME_APPLICATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_USER_SOURCE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
            UserSourceNotInSameApplication: ERROR_USER_SOURCE_NOT_IN_SAME_APPLICATION,
        }
    )
    @validate_body(MoveUserSourceSerializer)
    def patch(self, request, data: Dict, user_source_id: int):
        """
        Moves the user_source in the application before another user_source or at the
        end of the application if no before user_source is given.
        """

        user_source = UserSourceHandler().get_user_source_for_update(user_source_id)

        before_id = data.get("before_id", None)

        before = None
        if before_id:
            before = UserSourceHandler().get_user_source(before_id)

        moved_user_source = UserSourceService().move_user_source(
            request.user, user_source, before
        )

        serializer = user_source_type_registry.get_serializer(
            moved_user_source,
            UserSourceSerializer,
        )
        return Response(serializer.data)


class ListUserSourceUsersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The application we want the users for.",
            )
        ],
        tags=["User sources"],
        operation_id="list_application_user_source_users",
        description=("List per user sources the first 5 users available."),
        responses={
            200: UsersPerUserSourceSerializer,
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, application_id):
        """
        Responds with a list of serialized user_sources that belong to the application
        if the user has access to that application.
        """

        application = CoreHandler().get_application(application_id)

        user_sources = UserSourceService().get_user_sources(request.user, application)
        search = request.GET.get("search", "")

        users_per_user_sources = {}
        for user_source in user_sources:
            users_per_user_sources[user_source.id] = user_source.get_type().list_users(
                user_source, count=5, search=search
            )

        return Response(
            UsersPerUserSourceSerializer(
                SimpleNamespace(users_per_user_sources=users_per_user_sources)
            ).data
        )


class UserSourceObtainJSONWebToken(TokenObtainPairView):
    permission_classes = (AllowAny,)
    # We need the user to be authenticated for double authentication.
    authentication_classes = [
        JSONWebTokenAuthentication,
    ]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the user_source to move",
            ),
        ],
        tags=["User sources"],
        operation_id="user_source_token_auth",
        description=(
            "Authenticates an existing user against a user source "
            "based on their credentials. "
            "If successful, an access token and a refresh token will be returned."
        ),
        responses={
            200: authenticate_schema,
            401: {
                "description": "An active user with the provided email and password "
                "could not be found."
            },
        },
    )
    @map_exceptions(
        {
            AuthenticationFailed: ERROR_INVALID_CREDENTIALS,
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
            UserSourceImproperlyConfigured: ERROR_USER_SOURCE_IMPROPERLY_CONFIGURED,
        }
    )
    def post(self, request, user_source_id: int):
        """
        Return an access/refresh token pair if the given credentials matches for
        the given user source.
        """

        user_source = (
            UserSourceService()
            .get_user_source(request.user, user_source_id, for_authentication=True)
            .specific
        )

        serializer = UserSourceTokenObtainSerializer(user_source, data=request.data)

        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class UserSourceForceObtainJSONWebToken(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The user source to use to authenticate the user.",
            ),
        ],
        tags=["User sources"],
        operation_id="user_source_force_token_auth",
        description=(
            "Force authenticates an existing user based on their ID. "
            "If successful, an access token and a refresh token will be returned."
        ),
        responses={
            200: authenticate_schema,
            401: {
                "description": "An active user with the provided ID "
                "could not be found."
            },
        },
    )
    @map_exceptions(
        {
            AuthenticationFailed: ERROR_INVALID_CREDENTIALS,
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
        }
    )
    def post(self, request, user_source_id: int):
        """
        Returns JSON token pair for a user source for a given user ID.
        Used to authenticate without using the credentials.
        """

        user_source = (
            UserSourceService()
            .get_user_source(request.user, user_source_id, for_authentication=True)
            .specific
        )
        serializer = UserSourceForceTokenObtainSerializer(
            user_source, data=request.data
        )

        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class UserSourceTokenRefreshView(APIView):
    permission_classes = (AllowAny,)
    # We only want to authenticate with main auth
    authentication_classes = (JSONWebTokenAuthentication,)

    @extend_schema(
        tags=["User sources"],
        operation_id="user_source_token_refresh",
        description=(
            "Generate a new access_token that can be used to continue operating "
            "on Baserow with a user source user starting from a valid refresh token."
        ),
        responses={
            200: refresh_schema,
            401: {"description": "The JWT refresh token is invalid or expired."},
        },
    )
    @map_exceptions(
        {
            InvalidToken: ERROR_INVALID_REFRESH_TOKEN,
            UserSourceDoesNotExist: ERROR_USER_SOURCE_DOES_NOT_EXIST,
        }
    )
    def post(self, request, *args, **kwargs) -> Response:
        """
        Return a new access given a valid refresh token.
        """

        serializer = TokenRefreshSerializer(
            data=request.data, context={"user": request.user}
        )

        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class UserSourceBlacklistJSONWebToken(BlacklistJSONWebToken):
    permission_classes = ()
    authentication_classes = ()

    token_class = UserSourceToken

    @extend_schema(
        tags=["User sources"],
        operation_id="user_source_token_blacklist",
        description=(
            "Blacklists the provided user source token. "
            "This can be used the sign the user off."
        ),
        responses={
            204: None,
            401: {"description": "The JWT refresh token is invalid or expired."},
        },
        auth=[],
    )
    @map_exceptions(
        {
            InvalidToken: ERROR_INVALID_REFRESH_TOKEN,
            TokenError: ERROR_INVALID_REFRESH_TOKEN,
            RefreshTokenAlreadyBlacklisted: ERROR_REFRESH_TOKEN_ALREADY_BLACKLISTED,
        }
    )
    def post(self, request):
        return super().post(request)
