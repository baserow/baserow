from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.contrib.database.api.errors import ERROR_DATABASE_DOES_NOT_BELONG_TO_GROUP
from baserow.contrib.database.api.tables.errors import (
    ERROR_TABLE_DOES_NOT_BELONG_TO_GROUP,
)
from baserow.contrib.database.exceptions import DatabaseDoesNotBelongToGroup
from baserow.contrib.database.table.exceptions import TableDoesNotBelongToGroup
from baserow.contrib.database.tokens.actions import (
    CreateDbTokenActionType,
    DeleteDbTokenActionType,
    RotateDbTokenKeyActionType,
    UpdateDbTokenNameActionType,
    UpdateDbTokenPermissionsActionType,
)
from baserow.contrib.database.tokens.exceptions import TokenDoesNotExist
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.contrib.database.tokens.models import Token
from baserow.contrib.database.tokens.operations import UpdateTokenOperationType
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler

from .authentications import TokenAuthentication
from .errors import ERROR_TOKEN_DOES_NOT_EXIST
from .serializers import TokenCreateSerializer, TokenSerializer, TokenUpdateSerializer


class TokensView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Database tokens"],
        operation_id="list_database_tokens",
        description=(
            "Lists all the database tokens that belong to the authorized user. A token "
            "can be used to create, read, update and delete rows in the tables of the "
            "token's workspace. It only works on the tables if the token has the correct "
            "permissions. The **Database table rows** endpoints can be used for these "
            "operations."
        ),
        responses={
            200: TokenSerializer(many=True),
        },
    )
    def get(self, request):
        """Lists all the tokens of a user."""

        tokens = Token.objects.filter(
            user=request.user, workspace__workspaceuser__user=request.user
        ).prefetch_related("tokenpermission_set")
        serializer = TokenSerializer(tokens, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Database tokens"],
        operation_id="create_database_token",
        description=(
            "Creates a new database token for a given workspace and for the authorized user."
        ),
        request=TokenCreateSerializer,
        responses={
            200: TokenSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_REQUEST_BODY_VALIDATION"]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions({UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP})
    @validate_body(TokenCreateSerializer)
    def post(self, request, data):
        """Creates a new database token for the authorized user."""

        data["workspace"] = CoreHandler().get_workspace(data["workspace"])
        token = action_type_registry.get(CreateDbTokenActionType.type).do(
            request.user, data["workspace"], data["name"]
        )
        serializer = TokenSerializer(token)
        return Response(serializer.data)


class TokenView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="token_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the database token related to the provided value.",
            )
        ],
        tags=["Database tokens"],
        operation_id="get_database_token",
        description=(
            "Returns the requested database token if it is owned by the authorized user and"
            "if the user has access to the related workspace."
        ),
        responses={
            200: TokenSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_TOKEN_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TokenDoesNotExist: ERROR_TOKEN_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, token_id):
        """Responds with a serialized database token instance."""

        token = TokenHandler().get_token(request.user, token_id)
        serializer = TokenSerializer(token)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="token_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the database token related to the provided value.",
            )
        ],
        tags=["Database tokens"],
        operation_id="update_database_token",
        description=(
            "Updates the existing database token if it is owned by the authorized user and if"
            "the user has access to the related workspace."
        ),
        request=TokenUpdateSerializer,
        responses={
            200: TokenSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_DATABASE_DOES_NOT_BELONG_TO_GROUP",
                    "ERROR_TABLE_DOES_NOT_BELONG_TO_GROUP",
                ]
            ),
            404: get_error_schema(["ERROR_TOKEN_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            TokenDoesNotExist: ERROR_TOKEN_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            DatabaseDoesNotBelongToGroup: ERROR_DATABASE_DOES_NOT_BELONG_TO_GROUP,
            TableDoesNotBelongToGroup: ERROR_TABLE_DOES_NOT_BELONG_TO_GROUP,
        }
    )
    @validate_body(TokenUpdateSerializer)
    def patch(self, request, data, token_id):
        """Updates the values of a database token."""

        token = TokenHandler().get_token(
            request.user,
            token_id,
            base_queryset=Token.objects.select_for_update(of=("self",)),
        )

        CoreHandler().check_permissions(
            request.user,
            UpdateTokenOperationType.type,
            workspace=token.workspace,
            context=token,
        )

        permissions = data.pop("permissions", None)
        rotate_key = data.pop("rotate_key", False)

        if len(data) > 0:
            token = action_type_registry.get(UpdateDbTokenNameActionType.type).do(
                request.user, token, data["name"]
            )

        if permissions:
            action_type_registry.get(UpdateDbTokenPermissionsActionType.type).do(
                request.user, token, **permissions
            )

        if rotate_key:
            token = action_type_registry.get(RotateDbTokenKeyActionType.type).do(
                request.user, token
            )

        serializer = TokenSerializer(token)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="token_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the database token related to the provided value.",
            )
        ],
        tags=["Database tokens"],
        operation_id="delete_database_token",
        description=(
            "Deletes the existing database token if it is owned by the authorized user and if"
            "the user has access to the related workspace."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_TOKEN_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            TokenDoesNotExist: ERROR_TOKEN_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, token_id):
        """Deletes an existing database token."""

        token = TokenHandler().get_token(request.user, token_id)
        action_type_registry.get(DeleteDbTokenActionType.type).do(request.user, token)
        return Response(status=204)


class TokenCheckView(APIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Database tokens"],
        operation_id="check_database_token",
        description=(
            "This endpoint check be used to check if the provided personal API token "
            "is valid. If returns a `200` response if so and a `403` is not. This can "
            "be used by integrations like Zapier or n8n to test if a token is valid."
        ),
        responses={
            200: None,
            403: get_error_schema(["ERROR_TOKEN_DOES_NOT_EXIST"]),
        },
    )
    def get(self, request):
        return Response({"token": "OK"})
