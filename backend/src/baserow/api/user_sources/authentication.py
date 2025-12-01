from typing import Optional, Tuple, TypeVar

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import HTTP_HEADER_ENCODING, exceptions
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import Token

from baserow.core.exceptions import PermissionDenied, UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.models import Application
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.constants import USER_SOURCE_CLAIM
from baserow.core.user_sources.exceptions import UserSourceDoesNotExist
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.jwt_token import UserSourceAccessToken
from baserow.core.user_sources.operations import AuthenticateUserSourceOperationType
from baserow.core.user_sources.service import UserSourceService
from baserow.core.user_sources.user_source_user import UserSourceUser

AuthUser = TypeVar("AuthUser", AbstractBaseUser, UserSourceUser)


class NotUserSourceToken(Exception):
    """Raised when the given JWT token is not a user source user token"""


class UserSourceJSONWebTokenAuthentication(JWTAuthentication):
    """
    Authentication middleware that allow user source users to authenticate. All the
    authentication logic is delegated to the user source used to generate the token.
    """

    def __init__(
        self, use_user_source_authentication_header: bool = False, *args, **kwargs
    ):
        """
        :param use_user_source_authentication_header: Set to True if you want to
          authentication using a special `settings.USER_SOURCE_AUTHENTICATION_HEADER`
          header. This is useful when you want to keep the main authentication in the
          `Authorization` header but still want a "double" authentication with a user
          source user.
        """

        self.use_user_source_authentication_header = (
            use_user_source_authentication_header
        )
        super().__init__(*args, **kwargs)

    def get_header(self, request):
        if self.use_user_source_authentication_header:
            # Instead of reading the usual `Authorization` header we use a custom
            # header to authenticate the user source user.
            header = request.headers.get(
                settings.USER_SOURCE_AUTHENTICATION_HEADER, None
            )
            if isinstance(header, str):
                # Work around django test client oddness
                header = header.encode(HTTP_HEADER_ENCODING)

            return header
        else:
            return super().get_header(request)

    def authenticate(self, request: Request) -> Optional[Tuple[AuthUser, Token]]:
        """
        This method authenticate a user source user if the token has been generated
        by a user source.

        Returns a two-tuple of `User` and token if a valid signature has been
        supplied using JWT-based authentication. Otherwise returns `None`.
        """

        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            validated_token = UserSourceAccessToken(raw_token)
            user_source_uid = validated_token[USER_SOURCE_CLAIM]
            user_id = validated_token[jwt_settings.USER_ID_CLAIM]
        except (TokenError, KeyError):
            # Probably not a user source token let's skip this auth backend
            return None

        try:
            if self.use_user_source_authentication_header:
                # Using service here due to the "double authentication" situation.
                # This call has been triggered by the user source middleware
                # following initial DRF authentication.
                # The service ensures the authenticated user with the right
                # permissions regarding the user_source.
                user_source = UserSourceService().get_user_source_by_uid(
                    getattr(request, "user", AnonymousUser()),
                    user_source_uid,
                    for_authentication=True,
                )
            else:
                user_source = UserSourceHandler().get_user_source_by_uid(
                    user_source_uid,
                )
        except UserSourceDoesNotExist as exc:
            raise exceptions.AuthenticationFailed(
                detail={
                    "detail": "The user source does not exist",
                    "error": "user_source_does_not_exist",
                },
                code="user_source_does_not_exist",
            ) from exc
        except (PermissionDenied, UserNotInWorkspace) as exc:
            raise exceptions.AuthenticationFailed(
                detail={
                    "detail": (
                        "You are not allowed to use this user source to authenticate"
                    ),
                    "error": "user_source_not_allowed",
                },
                code="user_source_not_allowed",
            ) from exc
        except Application.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed(
                detail={
                    "detail": "The builder application was not found",
                    "error": "application_not_found",
                },
                code="application_not_found",
            ) from exc

        try:
            user = user_source.get_type().get_user(user_source, user_id=user_id)
        except UserNotFound as exc:
            raise exceptions.AuthenticationFailed(
                detail={"detail": "User not found", "error": "user_not_found"},
                code="user_not_found",
            ) from exc

        if not self.use_user_source_authentication_header:
            try:
                CoreHandler().check_permissions(
                    user,
                    AuthenticateUserSourceOperationType.type,
                    workspace=user_source.application.workspace,
                    context=user_source,
                )
            except (PermissionDenied, UserNotInWorkspace) as exc:
                raise exceptions.AuthenticationFailed(
                    detail={
                        "detail": (
                            "You are not allowed to use this user source to "
                            "authenticate"
                        ),
                        "error": "user_source_not_allowed",
                    },
                    code="user_source_not_allowed",
                ) from exc
            except Application.DoesNotExist as exc:
                raise exceptions.AuthenticationFailed(
                    detail={
                        "detail": "The builder application was not found",
                        "error": "application_not_found",
                    },
                    code="application_not_found",
                ) from exc

        return (
            user,
            validated_token,
        )


class UserSourceJSONWebTokenAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = (
        "baserow.api.user_sources.authentication.UserSourceJSONWebTokenAuthentication"
    )
    name = "UserSource JWT"
    match_subclasses = True
    priority = -1

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT your_token",
        }
