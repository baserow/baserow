from typing import List

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from itsdangerous.exc import BadSignature, BadTimeSignature, SignatureExpired
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.utils import datetime_from_epoch
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from baserow.api.actions.serializers import (
    UndoRedoResponseSerializer,
    get_undo_request_serializer,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import (
    BAD_TOKEN_SIGNATURE,
    ERROR_HOSTNAME_IS_NOT_ALLOWED,
    EXPIRED_TOKEN_SIGNATURE,
)
from baserow.api.schemas import get_error_schema
from baserow.api.sessions import (
    get_untrusted_client_session_id,
    set_user_session_data_from_request,
)
from baserow.api.user.registries import user_data_registry
from baserow.api.workspaces.invitations.errors import (
    ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
    ERROR_GROUP_INVITATION_EMAIL_MISMATCH,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import ActionScopeStr, action_type_registry
from baserow.core.auth_provider.exceptions import (
    AuthProviderDisabled,
    EmailVerificationRequired,
)
from baserow.core.auth_provider.handler import PasswordProviderHandler
from baserow.core.exceptions import (
    BaseURLHostnameNotAllowed,
    LockConflict,
    WorkspaceInvitationDoesNotExist,
    WorkspaceInvitationEmailMismatch,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import Settings, Template, WorkspaceInvitation
from baserow.core.user.actions import (
    ChangeEmailActionType,
    ChangeUserPasswordActionType,
    CreateUserActionType,
    ResetUserPasswordActionType,
    ScheduleUserDeletionActionType,
    SendChangeEmailConfirmationActionType,
    SendResetUserPasswordActionType,
    SendVerifyEmailAddressActionType,
    UpdateUserActionType,
    VerifyEmailAddressActionType,
)
from baserow.core.user.exceptions import (
    ChangeEmailNotAllowed,
    DeactivatedUserException,
    DisabledSignupError,
    EmailAlreadyChanged,
    EmailAlreadyVerified,
    InvalidPassword,
    InvalidVerificationToken,
    RefreshTokenAlreadyBlacklisted,
    ResetPasswordDisabledError,
    UserAlreadyExist,
    UserIsLastAdmin,
    UserNotFound,
)
from baserow.core.user.handler import UserHandler
from baserow.core.user.utils import generate_session_tokens_for_user

from .errors import (
    ERROR_ALREADY_EXISTS,
    ERROR_AUTH_PROVIDER_DISABLED,
    ERROR_CHANGE_EMAIL_NOT_ALLOWED,
    ERROR_CLIENT_SESSION_ID_HEADER_NOT_SET,
    ERROR_DEACTIVATED_USER,
    ERROR_DISABLED_RESET_PASSWORD,
    ERROR_DISABLED_SIGNUP,
    ERROR_EMAIL_ALREADY_CHANGED,
    ERROR_EMAIL_ALREADY_VERIFIED,
    ERROR_EMAIL_VERIFICATION_REQUIRED,
    ERROR_INVALID_CREDENTIALS,
    ERROR_INVALID_OLD_PASSWORD,
    ERROR_INVALID_REFRESH_TOKEN,
    ERROR_INVALID_VERIFICATION_TOKEN,
    ERROR_REFRESH_TOKEN_ALREADY_BLACKLISTED,
    ERROR_UNDO_REDO_LOCK_CONFLICT,
    ERROR_USER_IS_LAST_ADMIN,
    ERROR_USER_NOT_FOUND,
)
from .exceptions import ClientSessionIdHeaderNotSetException
from .schemas import (
    authenticate_user_schema,
    authenticated_user_response_schema,
    verify_user_schema,
)
from .serializers import (
    AccountSerializer,
    ChangeEmailSerializer,
    ChangePasswordBodyValidationSerializer,
    DashboardSerializer,
    RegisterSerializer,
    ResetPasswordBodyValidationSerializer,
    SendChangeEmailConfirmationSerializer,
    SendResetPasswordEmailBodyValidationSerializer,
    SendVerifyEmailAddressSerializer,
    ShareOnboardingDetailsWithBaserowSerializer,
    TokenBlacklistSerializer,
    TokenObtainPairWithUserSerializer,
    TokenRefreshWithUserSerializer,
    TokenVerifyWithUserSerializer,
    UserSerializer,
    VerifyEmailAddressSerializer,
    log_in_user,
)

User = get_user_model()
UndoRedoRequestSerializer = get_undo_request_serializer()


class ObtainJSONWebToken(TokenObtainPairView):
    """
    A slightly modified version of the ObtainJSONWebToken that uses an email as
    username and normalizes that email address using the normalize_email_address
    utility function.
    """

    serializer_class = TokenObtainPairWithUserSerializer

    @extend_schema(
        tags=["User"],
        operation_id="token_auth",
        description=(
            "Authenticates an existing user based on their email and their password. "
            "If successful, an access token and a refresh token will be returned. "
            "If the account is protected with two-factor authentication, "
            "temporary token is returned to finish the verification."
        ),
        responses={
            200: authenticated_user_response_schema,
            401: get_error_schema(
                [
                    "ERROR_INVALID_CREDENTIALS",
                    "ERROR_DEACTIVATED_USER",
                    "ERROR_AUTH_PROVIDER_DISABLED",
                    "ERROR_EMAIL_VERIFICATION_REQUIRED",
                ]
            ),
        },
        auth=[],
    )
    @map_exceptions(
        {
            AuthenticationFailed: ERROR_INVALID_CREDENTIALS,
            DeactivatedUserException: ERROR_DEACTIVATED_USER,
            AuthProviderDisabled: ERROR_AUTH_PROVIDER_DISABLED,
            EmailVerificationRequired: ERROR_EMAIL_VERIFICATION_REQUIRED,
        }
    )
    def post(self, *args, **kwargs):
        return super().post(*args, **kwargs)


class RefreshJSONWebToken(TokenRefreshView):
    serializer_class = TokenRefreshWithUserSerializer

    @extend_schema(
        tags=["User"],
        operation_id="token_refresh",
        description=(
            "Generate a new access_token that can be used to continue operating on Baserow "
            "starting from a valid refresh token."
        ),
        responses={
            200: authenticate_user_schema,
            401: get_error_schema(
                ["ERROR_INVALID_REFRESH_TOKEN", "ERROR_EMAIL_VERIFICATION_REQUIRED"]
            ),
        },
        auth=[],
    )
    @map_exceptions(
        {
            InvalidToken: ERROR_INVALID_REFRESH_TOKEN,
            EmailVerificationRequired: ERROR_EMAIL_VERIFICATION_REQUIRED,
        }
    )
    def post(self, *args, **kwargs):
        return super().post(*args, **kwargs)


class VerifyJSONWebToken(TokenVerifyView):
    serializer_class = TokenVerifyWithUserSerializer

    @extend_schema(
        tags=["User"],
        operation_id="token_verify",
        description=(
            "Verifies if the refresh token is valid and can be used "
            "to generate a new access_token."
        ),
        responses={
            200: verify_user_schema,
            401: get_error_schema(
                ["ERROR_INVALID_REFRESH_TOKEN", "ERROR_EMAIL_VERIFICATION_REQUIRED"]
            ),
        },
        auth=[],
    )
    @map_exceptions(
        {
            InvalidToken: ERROR_INVALID_REFRESH_TOKEN,
            EmailVerificationRequired: ERROR_EMAIL_VERIFICATION_REQUIRED,
        }
    )
    def post(self, *args, **kwargs):
        return super().post(*args, **kwargs)


class BlacklistJSONWebToken(TokenBlacklistView):
    permission_classes = ()
    authentication_classes = ()
    token_class = RefreshToken

    @extend_schema(
        tags=["User"],
        operation_id="token_blacklist",
        description=(
            "Blacklists the provided token. This can be used the sign the user off."
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
    @validate_body(TokenBlacklistSerializer)
    def post(self, request, data):
        refresh_token = data["refresh_token"]
        expires_at = datetime_from_epoch(self.token_class(refresh_token)["exp"])
        UserHandler().blacklist_refresh_token(refresh_token, expires_at)
        return Response(status=204)


class UserView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["User"],
        request=RegisterSerializer,
        operation_id="create_user",
        description=(
            "Creates a new user based on the provided values. If desired an "
            "authentication JWT can be generated right away. After creating an "
            "account the initial workspace containing a database is created."
        ),
        responses={
            200: authenticated_user_response_schema,
            400: get_error_schema(
                [
                    "ERROR_ALREADY_EXISTS",
                    "ERROR_GROUP_INVITATION_DOES_NOT_EXIST",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "BAD_TOKEN_SIGNATURE",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_INVITATION_DOES_NOT_EXIST"]),
        },
        auth=[],
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserAlreadyExist: ERROR_ALREADY_EXISTS,
            DeactivatedUserException: ERROR_DEACTIVATED_USER,
            BadSignature: BAD_TOKEN_SIGNATURE,
            WorkspaceInvitationDoesNotExist: ERROR_GROUP_INVITATION_DOES_NOT_EXIST,
            WorkspaceInvitationEmailMismatch: ERROR_GROUP_INVITATION_EMAIL_MISMATCH,
            DisabledSignupError: ERROR_DISABLED_SIGNUP,
            AuthProviderDisabled: ERROR_AUTH_PROVIDER_DISABLED,
        }
    )
    @validate_body(RegisterSerializer)
    def post(self, request, data):
        """Registers a new user."""

        if not PasswordProviderHandler.get().enabled:
            raise AuthProviderDisabled()

        template = (
            Template.objects.get(pk=data["template_id"])
            if data["template_id"]
            else None
        )

        user = action_type_registry.get(CreateUserActionType.type).do(
            name=data["name"],
            email=data["email"],
            password=data["password"],
            language=data["language"],
            workspace_invitation_token=data.get("workspace_invitation_token"),
            template=template,
        )

        response = {"user": UserSerializer(user).data}

        settings = CoreHandler().get_settings()

        if (
            data["authenticate"]
            and settings.email_verification
            != Settings.EmailVerificationOptions.ENFORCED
        ):
            response |= {
                **generate_session_tokens_for_user(
                    user,
                    verified_email_claim=Settings.EmailVerificationOptions.ENFORCED,
                    include_refresh_token=True,
                ),
                **user_data_registry.get_all_user_data(user, request),
            }

        return Response(response)


class SendResetPasswordEmailView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["User"],
        request=SendResetPasswordEmailBodyValidationSerializer,
        operation_id="send_password_reset_email",
        description=(
            "Sends an email containing the password reset link to the email address "
            "of the user. This will only be done if a user is found with the given "
            "email address. The endpoint will not fail if the email address is not "
            "found. The link is going to the valid for {valid} hours.".format(
                valid=int(settings.RESET_PASSWORD_TOKEN_MAX_AGE / 60 / 60)
            )
        ),
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_HOSTNAME_IS_NOT_ALLOWED"]
            ),
        },
        auth=[],
    )
    @transaction.atomic
    @validate_body(SendResetPasswordEmailBodyValidationSerializer)
    @map_exceptions(
        {
            BaseURLHostnameNotAllowed: ERROR_HOSTNAME_IS_NOT_ALLOWED,
            ResetPasswordDisabledError: ERROR_DISABLED_RESET_PASSWORD,
            AuthProviderDisabled: ERROR_AUTH_PROVIDER_DISABLED,
        }
    )
    def post(self, request, data):
        """
        If the email is found, an email containing the password reset link is send to
        the user.
        """

        handler = UserHandler()

        try:
            user = handler.get_active_user(email=data["email"])
            if not PasswordProviderHandler.get().enabled and user.is_staff is False:
                raise AuthProviderDisabled()

            set_user_session_data_from_request(user, request)
            action_type_registry.get(SendResetUserPasswordActionType.type).do(
                user, data["base_url"]
            )
        except UserNotFound:
            pass

        return Response(status=204)


class ResetPasswordView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["User"],
        request=ResetPasswordBodyValidationSerializer,
        operation_id="reset_password",
        description=(
            "Changes the password of a user if the reset token is valid. The "
            "**send_password_reset_email** endpoint sends an email to the user "
            "containing the token. That token can be used to change the password "
            "here without providing the old password."
        ),
        responses={
            204: None,
            400: get_error_schema(
                [
                    "BAD_TOKEN_SIGNATURE",
                    "EXPIRED_TOKEN_SIGNATURE",
                    "ERROR_USER_NOT_FOUND",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
        },
        auth=[],
    )
    @transaction.atomic
    @map_exceptions(
        {
            BadSignature: BAD_TOKEN_SIGNATURE,
            BadTimeSignature: BAD_TOKEN_SIGNATURE,
            SignatureExpired: EXPIRED_TOKEN_SIGNATURE,
            UserNotFound: ERROR_USER_NOT_FOUND,
            ResetPasswordDisabledError: ERROR_DISABLED_RESET_PASSWORD,
        }
    )
    @validate_body(ResetPasswordBodyValidationSerializer)
    def post(self, request, data):
        """Changes users password if the provided reset token is valid."""

        action_type_registry.get(ResetUserPasswordActionType.type).do(
            data["token"], data["password"]
        )

        return Response(status=204)


class ChangePasswordView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["User"],
        request=ChangePasswordBodyValidationSerializer,
        operation_id="change_password",
        description=(
            "Changes the password of an authenticated user, but only if the old "
            "password matches."
        ),
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_INVALID_OLD_PASSWORD",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            InvalidPassword: ERROR_INVALID_OLD_PASSWORD,
            AuthProviderDisabled: ERROR_AUTH_PROVIDER_DISABLED,
        }
    )
    @validate_body(ChangePasswordBodyValidationSerializer)
    def post(self, request, data):
        """Changes the authenticated user's password if the old password is correct."""

        if not PasswordProviderHandler.get().enabled and request.user.is_staff is False:
            raise AuthProviderDisabled()
        action_type_registry.get(ChangeUserPasswordActionType.type).do(
            request.user, data["old_password"], data["new_password"]
        )

        return Response(status=204)


class SendChangeEmailConfirmationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["User"],
        request=SendChangeEmailConfirmationSerializer,
        operation_id="send_change_email_confirmation",
        description=(
            "Sends an email to the new email address containing a confirmation link. "
            "The user must provide their current password to initiate this request. "
            f"The link is going to be valid for "
            f"{int(settings.CHANGE_EMAIL_TOKEN_MAX_AGE / 60 / 60)} hours."
        ),
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_HOSTNAME_IS_NOT_ALLOWED",
                    "ERROR_INVALID_OLD_PASSWORD",
                    "ERROR_ALREADY_EXISTS",
                    "ERROR_CHANGE_EMAIL_NOT_ALLOWED",
                    "ERROR_AUTH_PROVIDER_DISABLED",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            BaseURLHostnameNotAllowed: ERROR_HOSTNAME_IS_NOT_ALLOWED,
            InvalidPassword: ERROR_INVALID_OLD_PASSWORD,
            UserAlreadyExist: ERROR_ALREADY_EXISTS,
            AuthProviderDisabled: ERROR_AUTH_PROVIDER_DISABLED,
            ChangeEmailNotAllowed: ERROR_CHANGE_EMAIL_NOT_ALLOWED,
        }
    )
    @validate_body(SendChangeEmailConfirmationSerializer)
    def post(self, request, data):
        """
        Sends a confirmation email to the new email address if the password is correct.
        """

        action_type_registry.get(SendChangeEmailConfirmationActionType.type).do(
            request.user, data["new_email"], data["password"], data["base_url"]
        )

        return Response(status=204)


class ChangeEmailView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["User"],
        request=ChangeEmailSerializer,
        operation_id="change_email",
        description=(
            "Changes the email address of a user if the confirmation token is valid. "
            "The **send_change_email_confirmation** endpoint sends an email to the "
            "new address containing the token. That token can be used to change the "
            "email address here."
        ),
        responses={
            204: None,
            400: get_error_schema(
                [
                    "BAD_TOKEN_SIGNATURE",
                    "EXPIRED_TOKEN_SIGNATURE",
                    "ERROR_USER_NOT_FOUND",
                    "ERROR_ALREADY_EXISTS",
                    "ERROR_EMAIL_ALREADY_CHANGED",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
        },
        auth=[],
    )
    @transaction.atomic
    @map_exceptions(
        {
            BadSignature: BAD_TOKEN_SIGNATURE,
            BadTimeSignature: BAD_TOKEN_SIGNATURE,
            SignatureExpired: EXPIRED_TOKEN_SIGNATURE,
            UserNotFound: ERROR_USER_NOT_FOUND,
            UserAlreadyExist: ERROR_ALREADY_EXISTS,
            EmailAlreadyChanged: ERROR_EMAIL_ALREADY_CHANGED,
        }
    )
    @validate_body(ChangeEmailSerializer)
    def post(self, request, data):
        """Changes the user's email address if the provided token is valid."""

        action_type_registry.get(ChangeEmailActionType.type).do(data["token"])

        return Response(status=204)


class AccountView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["User"],
        request=AccountSerializer,
        operation_id="update_account",
        description="Updates the account information of the authenticated user.",
        responses={
            200: AccountSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
        },
    )
    @transaction.atomic
    @validate_body(AccountSerializer)
    def patch(self, request, data):
        """Updates editable user account information."""

        user = action_type_registry.get(UpdateUserActionType.type).do(
            request.user, **data
        )
        return Response(AccountSerializer(user).data)


class SendVerifyEmailView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["User"],
        operation_id="send_verify_email",
        description=(
            "Sends an email to the user "
            "with an email verification link "
            "if the user's email is not verified yet."
        ),
        responses={
            204: None,
        },
    )
    @transaction.atomic
    @validate_body(SendVerifyEmailAddressSerializer)
    def post(self, request, data):
        """
        Sends a verify email link to the user.
        """

        try:
            handler = UserHandler()
            user = handler.get_active_user(email=data["email"])
            action_type_registry.get(SendVerifyEmailAddressActionType.type).do(user)
        except (EmailAlreadyVerified, UserNotFound):
            # ignore as not to leak existing email addresses
            ...
        return Response(status=204)


class VerifyEmailAddressView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["User"],
        request=VerifyEmailAddressSerializer,
        operation_id="verify_email",
        description=(
            "Passing the correct verification token will "
            "confirm that the user's email address belongs to "
            "the user. This endpoint also optionally returns "
            "user information, access token and the refresh token "
            "for automatically signing user in the system if the "
            "request is performed by unauthenticated user."
        ),
        responses={
            200: authenticated_user_response_schema,
            400: get_error_schema(
                [
                    "ERROR_INVALID_VERIFICATION_TOKEN",
                    "ERROR_EMAIL_ALREADY_VERIFIED",
                ]
            ),
            401: get_error_schema(
                [
                    "ERROR_DEACTIVATED_USER",
                    "ERROR_AUTH_PROVIDER_DISABLED",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            InvalidVerificationToken: ERROR_INVALID_VERIFICATION_TOKEN,
            EmailAlreadyVerified: ERROR_EMAIL_ALREADY_VERIFIED,
            DeactivatedUserException: ERROR_DEACTIVATED_USER,
            AuthProviderDisabled: ERROR_AUTH_PROVIDER_DISABLED,
        }
    )
    @validate_body(VerifyEmailAddressSerializer)
    def post(self, request, data):
        """
        Verifies that the user's email belong to the user.
        """

        user = action_type_registry.get(VerifyEmailAddressActionType.type).do(
            data["token"]
        )

        if request.user.is_anonymous:
            data = log_in_user(request, user)
            return Response(status=200, data=data)
        else:
            return Response(status=200, data={"email": user.email})


class ScheduleAccountDeletionView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["User"],
        operation_id="schedule_account_deletion",
        description=(
            "Schedules the account deletion of the authenticated user. "
            "The user will be permanently deleted after the grace delay defined "
            "by the instance administrator."
        ),
        request=None,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserIsLastAdmin: ERROR_USER_IS_LAST_ADMIN,
        }
    )
    def post(self, request):
        """Schedules user account deletion."""

        action_type_registry.get(ScheduleUserDeletionActionType.type).do(request.user)
        return Response(status=204)


class DashboardView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["User"],
        operation_id="dashboard",
        description=(
            "Lists all the relevant user information that for example could be shown "
            "on a dashboard. It will contain all the pending workspace invitations for "
            "that user."
        ),
        responses={200: DashboardSerializer},
    )
    @transaction.atomic
    def get(self, request):
        """Lists all the data related to the user dashboard page."""

        workspace_invitations = WorkspaceInvitation.objects.select_related(
            "workspace", "invited_by"
        ).filter(email=request.user.username)
        dashboard_serializer = DashboardSerializer(
            {"workspace_invitations": workspace_invitations}
        )
        return Response(dashboard_serializer.data)


UNDO_REDO_EXCEPTIONS_MAP = {
    ClientSessionIdHeaderNotSetException: ERROR_CLIENT_SESSION_ID_HEADER_NOT_SET,
    LockConflict: ERROR_UNDO_REDO_LOCK_CONFLICT,
}


class UndoView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name=settings.CLIENT_SESSION_ID_HEADER,
                location=OpenApiParameter.HEADER,
                type=OpenApiTypes.UUID,
                required=True,
                description="The particular client session to undo actions for. The "
                "actions must have been performed with this same header set with the "
                "same value for them to be undoable by this endpoint.",
            )
        ],
        tags=["User"],
        request=UndoRedoRequestSerializer,
        operation_id="undo",
        description=(
            "undoes the latest undoable action performed by the user making the "
            f"request. a {settings.CLIENT_SESSION_ID_HEADER} header must be provided "
            f"and only actions which were performed the same user with the same "
            f"{settings.CLIENT_SESSION_ID_HEADER} value set on the api request that "
            f"performed the action will be undone."
            f"Additionally the {settings.CLIENT_SESSION_ID_HEADER} header must "
            f"be between 1 and {settings.MAX_CLIENT_SESSION_ID_LENGTH} characters long "
            f"and must only contain alphanumeric or the - characters."
        ),
        responses={200: UndoRedoResponseSerializer},
    )
    @validate_body(UndoRedoRequestSerializer)
    @map_exceptions(UNDO_REDO_EXCEPTIONS_MAP)
    @transaction.atomic
    def patch(self, request, data: List[ActionScopeStr]):
        session_id = get_untrusted_client_session_id(request.user)
        if session_id is None:
            raise ClientSessionIdHeaderNotSetException()
        undone_actions = ActionHandler.undo(request.user, data, session_id)
        serializer = UndoRedoResponseSerializer({"actions": undone_actions})
        return Response(serializer.data, status=200)


class RedoView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name=settings.CLIENT_SESSION_ID_HEADER,
                location=OpenApiParameter.HEADER,
                type=OpenApiTypes.UUID,
                required=True,
                description="The particular client session to redo actions for. The "
                "actions must have been performed with this same header set with the "
                "same value for them to be redoable by this endpoint.",
            )
        ],
        tags=["User"],
        request=UndoRedoRequestSerializer,
        operation_id="redo",
        description=(
            "Redoes the latest redoable action performed by the user making the "
            f"request. a {settings.CLIENT_SESSION_ID_HEADER} header must be provided "
            f"and only actions which were performed the same user with the same "
            f"{settings.CLIENT_SESSION_ID_HEADER} value set on the api request that "
            f"performed the action will be redone."
            f"Additionally the {settings.CLIENT_SESSION_ID_HEADER} header must "
            f"be between 1 and {settings.MAX_CLIENT_SESSION_ID_LENGTH} characters long "
            f"and must only contain alphanumeric or the - characters."
        ),
        responses={200: UndoRedoResponseSerializer},
    )
    @validate_body(UndoRedoRequestSerializer)
    @map_exceptions(UNDO_REDO_EXCEPTIONS_MAP)
    @transaction.atomic
    def patch(self, request, data: List[ActionScopeStr]):
        session_id = get_untrusted_client_session_id(request.user)
        if session_id is None:
            raise ClientSessionIdHeaderNotSetException()
        redone_actions = ActionHandler.redo(request.user, data, session_id)
        serializer = UndoRedoResponseSerializer({"actions": redone_actions})
        return Response(serializer.data, status=200)


class ShareOnboardingDetailsWithBaserowView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(exclude=True)
    @transaction.atomic
    @validate_body(ShareOnboardingDetailsWithBaserowSerializer)
    def post(self, request, data):
        UserHandler().start_share_onboarding_details_with_baserow(
            request.user, data["team"], data["role"], data["size"], data["country"]
        )

        return Response(status=204)
