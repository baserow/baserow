from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.core.action.registries import action_type_registry
from baserow.core.auth_provider.exceptions import (
    CannotDisableLastAuthProvider,
    DifferentAuthProvider,
)
from baserow.core.auth_provider.handler import PasswordProviderHandler
from baserow.core.auth_provider.models import (
    AuthProviderModel,
    PasswordAuthProviderModel,
)
from baserow.core.auth_provider.registries import BaseAuthProviderType
from baserow.core.auth_provider.types import AuthProviderModelSubClass, UserInfo
from baserow.core.auth_provider.validators import validate_domain
from baserow.core.handler import CoreHandler
from baserow.core.user.exceptions import UserNotFound


class AuthProviderType(BaseAuthProviderType):
    """
    Base auth provider type class for Baserow auth providers.
    """

    def before_update(
        self, user: AbstractUser, auth_provider: AuthProviderModelSubClass, **values
    ):
        """
        This hook is called before the authentication provider is updated.

        :param user: The user that is updating the authentication provider.
        :param provider: The authentication provider that is being updated.
        :param values: The values that are used to update the authentication provider.
        """

        super().before_update(user, auth_provider, **values)

        enabled_next = values.get("enabled", None)
        if enabled_next is False:
            another_enabled = (
                AuthProviderModel.objects.filter(enabled=True)
                .exclude(id=auth_provider.id)
                .exists()
            )
            if not another_enabled:
                raise CannotDisableLastAuthProvider()

    def before_delete(
        self, user: AbstractUser, auth_provider: AuthProviderModelSubClass
    ):
        """
        This hook is called before the authentication provider is deleted.

        :param user: The user that is deleting the authentication provider.
        :param provider: The authentication provider that is being deleted.
        """

        super().before_delete(user, auth_provider)

        another_enabled = (
            AuthProviderModel.objects.filter(enabled=True)
            .exclude(id=auth_provider.id)
            .exists()
        )
        if not another_enabled:
            raise CannotDisableLastAuthProvider()

    def get_or_create_user_and_sign_in(
        self, auth_provider: AuthProviderModelSubClass, user_info: UserInfo
    ) -> [AbstractUser, bool]:
        """
        Gets from the database if present or creates a user if not, based on the
        user info that was received from the identity provider.

        :param auth_provider: The authentication provider that was used to
            authenticate the user.
        :param user_info: A dataclass containing the user info that can be sent
            to the UserHandler().create_user() method.
        :raises DeactivatedUserException: If the user exists but has been
            disabled from an admin.
        :return: The user that was created or retrieved and a boolean flag set
            to True if the user has been created, False otherwise.
        """

        try:
            user = self.get_user_and_sign_in(auth_provider, user_info)
            created = False
        except UserNotFound:
            user = self.create_user(auth_provider, user_info)
            created = True

        return user, created

    def get_user_and_sign_in(
        self, auth_provider: AuthProviderModelSubClass, user_info: UserInfo
    ) -> AbstractUser:
        """
        Returns the user according to the given user_info.

        :param auth_provider: The authentication provider that was used to
            authenticate the user.
        :param user_info: The user info to use to get the user.
        :raises DeactivatedUserException: If the user exists but has been
            disabled from an admin.
        :raises DifferentAuthProvider: If the user exists but has been
            created using a different auth provider.
        :return: a user instance.
        """

        from baserow.core.actions import AcceptWorkspaceInvitationActionType
        from baserow.core.user.actions import SignInUserActionType
        from baserow.core.user.handler import UserHandler

        user = UserHandler().get_active_user(email=user_info.email)

        is_original_provider_check_needed = (
            not settings.BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT
            and not auth_provider.allow_existing_users
        )
        if (
            is_original_provider_check_needed
            and not auth_provider.users.filter(id=user.id).exists()
        ):
            raise DifferentAuthProvider()

        action_type_registry.get(SignInUserActionType.type).do(user, auth_provider)

        if user_info.workspace_invitation_token:
            core_handler = CoreHandler()
            invitation = core_handler.get_workspace_invitation_by_token(
                user_info.workspace_invitation_token
            )
            action_type_registry.get(AcceptWorkspaceInvitationActionType.type).do(
                user, invitation
            )

        return user

    def create_user(
        self, auth_provider: AuthProviderModelSubClass, user_info: UserInfo
    ) -> AbstractUser:
        """
        Creates the user according to the given user_info.

        :param auth_provider: The authentication provider that was used to
            authenticate the user.
        :param user_info: A dataclass containing the user info that can be sent
            to the UserHandler().create_user() method.
        :return: a user instance.
        """

        from baserow.core.user.actions import CreateUserActionType

        return action_type_registry.get(CreateUserActionType.type).do(
            name=user_info.name,
            email=user_info.email,
            password=None,
            language=user_info.language,
            workspace_invitation_token=user_info.workspace_invitation_token,
            auth_provider=auth_provider,
        )

    def export_serialized(self) -> Dict[str, Any]:
        """
        Returns the serialized data for this authentication provider type.
        """

        from baserow.api.auth_provider.serializers import AuthProviderSerializer

        return {
            "type": self.type,
            "can_create_new": self.can_create_new_providers(),
            "can_delete_existing": self.can_delete_existing_providers(),
            "auth_providers": [
                self.get_serializer(provider, AuthProviderSerializer).data
                for provider in self.list_providers()
            ],
        }

    def import_serialized(
        self, parent: Any, serialized_values: Dict[str, Any], id_mapping: Dict
    ) -> Any:
        raise NotImplementedError()


class PasswordAuthProviderType(AuthProviderType):
    """
    The password authentication provider type is the default authentication provider
    type that is always available. It allows users to login with their email address
    and password.
    """

    type = "password"
    model_class = PasswordAuthProviderModel
    allowed_fields = ["id", "enabled"]
    serializer_field_names = ["enabled"]
    serializer_field_overrides = {
        "domain": serializers.CharField(
            validators=[validate_domain],
            required=False,
            help_text="The email domain (if any) registered with this password provider.",
        ),
        "enabled": serializers.BooleanField(
            help_text="Whether the provider is enabled or not.",
            required=False,
        ),
    }

    def get_login_options(self, **kwargs) -> Optional[Dict[str, Any]]:
        if not PasswordProviderHandler.get().enabled:
            return None
        return {"type": self.type}

    def can_create_new_providers(self, **kwargs):
        return False

    def can_delete_existing_providers(self):
        return False
