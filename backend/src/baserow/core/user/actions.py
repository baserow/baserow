import dataclasses
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import RootActionScopeType
from baserow.core.auth_provider.handler import PasswordProviderHandler
from baserow.core.auth_provider.models import AuthProviderModel
from baserow.core.models import Template, User
from baserow.core.registries import auth_provider_type_registry
from baserow.core.user.handler import UserHandler
from baserow.throttling import rate_limit


class CreateUserActionType(ActionType):
    type = "create_user"
    description = ActionTypeDescription(
        _("Create User"),
        _(
            'User "%(user_email)s" (%(user_id)s) created via "%(auth_provider_type)s"'
            " (%(auth_provider_id)s) auth provider (invitation: %(with_invitation_token)s)"
        ),
    )
    analytics_params = [
        "user_id",
        "auth_provider_id",
        "workspace_id",
        "with_invitation_token",
        "template_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str
        auth_provider_id: int
        auth_provider_type: str
        workspace_id: Optional[int] = None
        workspace_name: Optional[str] = ""
        with_invitation_token: bool = False
        template_id: Optional[int] = None

    @classmethod
    def do(
        cls,
        name: str,
        email: str,
        password: str,
        language: str,
        workspace_invitation_token: Optional[str] = None,
        template: Optional[Template] = None,
        auth_provider: Optional[AuthProviderModel] = None,
    ) -> AbstractUser:
        """
        Creates a new user.

        :param name: The name of the user.
        :param email: The email address of the user.
        :param password: The password of the user.
        :param language: The language of the user.
        :param workspace_invitation_token: The workspace invitation token that will be
            used to add the user to a workspace.
        :param template: The template that will be used to create the user.
        :param auth_provider: The auth provider that will be used to create the user.

        :return: The created user.
        """

        if auth_provider is None:
            auth_provider = PasswordProviderHandler.get()

        user = UserHandler().create_user(
            name,
            email,
            password,
            language,
            workspace_invitation_token,
            template,
            auth_provider=auth_provider,
        )

        workspace_id, workspace_name = None, None
        if user.default_workspace:
            workspace_id = user.default_workspace.id
            workspace_name = user.default_workspace.name

        cls.register_action(
            user=user,
            params=cls.Params(
                user.id,
                user.email,
                auth_provider.id,
                auth_provider_type_registry.get_by_model(auth_provider).type,
                workspace_id,
                workspace_name,
                workspace_invitation_token is not None,
                template.id if template else None,
            ),
            scope=cls.scope(),
            workspace=user.default_workspace,
        )
        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class UpdateUserActionType(ActionType):
    type = "update_user"
    description = ActionTypeDescription(
        _("Update User"),
        _('User "%(user_email)s" (%(user_id)s) updated'),
    )
    analytics_params = [
        "user_id",
        "language",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str
        first_name: Optional[str]
        language: Optional[str]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        first_name: Optional[str] = None,
        language: Optional[str] = None,
        email_notification_frequency: Optional[str] = None,
        completed_onboarding: Optional[bool] = None,
        completed_guided_tours: Optional[str] = None,
        **kwargs: Any,
    ) -> AbstractUser:
        """
        Updates user's data.

        :param user: The user that will be updated.
        :param first_name: The first name of the user.
        :param language: The language of the user.
        :param email_notification_frequency: The frequency chosen by the user to
            receive email notifications.
        :param completed_onboarding: Indicates whether the user has already completed
            the onboarding.
        :param completed_guided_tours: List containing the guided tour types that
            have been completed.
        :return: The updated user.
        """

        user = UserHandler().update_user(
            user,
            first_name=first_name,
            language=language,
            email_notification_frequency=email_notification_frequency,
            completed_onboarding=completed_onboarding,
            completed_guided_tours=completed_guided_tours,
        )

        cls.register_action(
            user=user,
            params=cls.Params(user.id, user.email, first_name, language),
            scope=cls.scope(),
        )
        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class ScheduleUserDeletionActionType(ActionType):
    type = "schedule_user_deletion"
    description = ActionTypeDescription(
        _("Schedule user deletion"),
        _(
            'User "%(user_email)s" (%(user_id)s) scheduled to be deleted after grace time'
        ),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(cls, user: AbstractUser) -> AbstractUser:
        """
        Schedules the user for deletion.

        :param user: The user that will be updated.
        """

        UserHandler().schedule_user_deletion(user)

        cls.register_action(
            user=user, params=cls.Params(user.id, user.email), scope=cls.scope()
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class CancelUserDeletionActionType(ActionType):
    type = "cancel_user_deletion"
    description = ActionTypeDescription(
        _("Cancel user deletion"),
        _(
            'User "%(user_email)s" (%(user_id)s) logged in cancelling the deletion process'
        ),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(cls, user: AbstractUser) -> AbstractUser:
        """
        Stops the deletion process for the user.

        :param user: The user that will be updated.
        """

        UserHandler().cancel_user_deletion(user)

        cls.register_action(
            user=user, params=cls.Params(user.id, user.email), scope=cls.scope()
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class SignInUserActionType(ActionType):
    type = "sign_in_user"
    description = ActionTypeDescription(
        _("Sign In User"),
        _(
            'User "%(user_email)s" (%(user_id)s) signed in via '
            '"%(auth_provider_type)s" (%(auth_provider_id)s) auth provider'
        ),
    )
    analytics_params = [
        "user_id",
        "auth_provider_id",
        "auth_provider_type",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str
        auth_provider_id: Optional[int] = None
        auth_provider_type: Optional[str] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        auth_provider: Optional[AuthProviderModel] = None,
    ):
        """
        Sign in the user into Baserow.

        :param user: The user that sign in.
        :param auth_provider: The authentication provider that was used to
            sign in the user.
        """

        handler = UserHandler()
        if auth_provider is None:
            auth_provider = PasswordProviderHandler.get()

        auth_provider_id = auth_provider.id
        auth_provider_type = auth_provider_type_registry.get_by_model(
            auth_provider
        ).type

        # This check must always be performed, even if the `log_signin_action` call is
        # rate limited.
        if user.profile.to_be_deleted:
            UserHandler().cancel_user_deletion(user)

        def log_signin_action():
            handler.user_signed_in_via_provider(user, auth_provider)
            cls.register_action(
                user=user,
                params=cls.Params(
                    user.id, user.email, auth_provider_id, auth_provider_type
                ),
                scope=cls.scope(),
            )

        rate_limit(
            rate=settings.BASEROW_LOGIN_ACTION_LOG_LIMIT,
            key=f"{user.username}:{type(auth_provider).__name__}",
            raise_exception=False,
        )(log_signin_action)()

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class SendResetUserPasswordActionType(ActionType):
    type = "send_reset_user_password"
    description = ActionTypeDescription(
        _("Send reset user password"),
        _('User "%(user_email)s" (%(user_id)s) requested to reset password'),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(cls, user: AbstractUser, base_url: str):
        """
        Send a reset password email to the user.

        :param user: The user that will be updated.
        """

        UserHandler().send_reset_password_email(user, base_url)

        cls.register_action(
            user=user, params=cls.Params(user.id, user.email), scope=cls.scope()
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class ChangeUserPasswordActionType(ActionType):
    type = "change_user_password"
    description = ActionTypeDescription(
        _("Change user password"),
        _('User "%(user_email)s" (%(user_id)s) changed password'),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(
        cls, user: AbstractUser, old_password: str, new_password: str
    ) -> AbstractUser:
        """
        Change the user password.

        :param user: The user that will be updated.
        :param old_password: The old password of the user.
        :param new_password: The new password of the user.
        :return: The updated user.
        """

        user = UserHandler().change_password(user, old_password, new_password)

        cls.register_action(
            user=user, params=cls.Params(user.id, user.email), scope=cls.scope()
        )
        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class ResetUserPasswordActionType(ActionType):
    type = "reset_user_password"
    description = ActionTypeDescription(
        _("Reset user password"),
        _('User "%(user_email)s" (%(user_id)s) reset password'),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(cls, token: str, password: str) -> AbstractUser:
        """
        Reset the user password.

        :param user: The user that will be updated.
        :param password: The new password of the user.
        :return: The updated user.
        """

        user = UserHandler().reset_password(token, password)

        cls.register_action(
            user=user, params=cls.Params(user.id, user.email), scope=cls.scope()
        )
        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class SendVerifyEmailAddressActionType(ActionType):
    type = "send_verify_email"
    description = ActionTypeDescription(
        _("Send verify email"),
        _('User "%(user_email)s" (%(user_id)s) requested to verify email'),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(cls, user: User):
        """
        Sends an email verification email to the user.
        """

        UserHandler().send_email_pending_verification(user)

        cls.register_action(
            user=user, params=cls.Params(user.id, user.email), scope=cls.scope()
        )

        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class VerifyEmailAddressActionType(ActionType):
    type = "verify_email"
    description = ActionTypeDescription(
        _("Verify email"),
        _('User "%(user_email)s" (%(user_id)s) verify email'),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str

    @classmethod
    def do(cls, verification_token: str):
        """
        Confirm that the associated email address
        belongs to the user.

        :param verification_token: The secret token to
            verify that the email belongs to the user.
        """

        user = UserHandler().verify_email_address(verification_token)

        cls.register_action(
            user=user, params=cls.Params(user.id, user.email), scope=cls.scope()
        )

        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class SendChangeEmailConfirmationActionType(ActionType):
    type = "send_change_email_confirmation"
    description = ActionTypeDescription(
        _("Send change email confirmation"),
        _(
            'User "%(user_email)s" (%(user_id)s) requested to change email to '
            '"%(new_email)s"'
        ),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        user_email: str
        new_email: str

    @classmethod
    def do(
        cls, user: AbstractUser, new_email: str, password: str, base_url: str
    ) -> AbstractUser:
        """
        Send a change email confirmation email to the new email address.

        :param user: The user that requested the email change.
        :param new_email: The new email address.
        :param password: The current password for verification.
        :param base_url: The base URL for the confirmation link.
        """

        UserHandler().send_change_email_confirmation(
            user, new_email, password, base_url
        )

        cls.register_action(
            user=user,
            params=cls.Params(user.id, user.email, new_email),
            scope=cls.scope(),
        )
        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class ChangeEmailActionType(ActionType):
    type = "change_email"
    description = ActionTypeDescription(
        _("Change email"),
        _(
            'User "%(old_email)s" (%(user_id)s) changed email to "%(new_email)s" by '
            "using the token."
        ),
    )
    analytics_params = [
        "user_id",
    ]

    @dataclasses.dataclass
    class Params:
        user_id: int
        old_email: str
        new_email: str

    @classmethod
    def do(cls, token: str) -> AbstractUser:
        """
        Change the user's email address if the provided confirmation token is valid.

        :param token: The confirmation token to check whether it's valid.
        :return: The updated user object.
        """

        handler = UserHandler()
        user, old_email = handler.change_email(token)

        cls.register_action(
            user=user,
            params=cls.Params(user.id, old_email, user.email),
            scope=cls.scope(),
        )
        return user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()
