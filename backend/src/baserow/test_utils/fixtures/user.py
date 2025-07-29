from typing import Tuple

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from baserow.api.sessions import (
    set_user_websocket_id,
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
)
from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    UserProfile,
    WorkspaceUser,
)

User = get_user_model()


class UserFixtures:
    def generate_token(self, user):
        return str(AccessToken.for_user(user))

    def generate_refresh_token(self, user):
        return str(RefreshToken.for_user(user))

    def create_user(self, **kwargs) -> AbstractUser:
        profile_data = {}

        if "email" not in kwargs:
            kwargs["email"] = self.fake.unique.email()

        if "username" not in kwargs:
            kwargs["username"] = kwargs["email"]

        if "first_name" not in kwargs:
            kwargs["first_name"] = self.fake.name()

        if "password" not in kwargs:
            kwargs["password"] = "password"

        session_id = kwargs.pop("session_id", "default-test-user-session-id")
        action_group = kwargs.pop("action_group", None)
        web_socket_id = kwargs.pop("web_socket_id", None)

        profile_data["language"] = kwargs.pop("language", "en")
        profile_data["to_be_deleted"] = kwargs.pop("to_be_deleted", False)
        profile_data["concurrency_limit"] = kwargs.pop("concurrency_limit", None)
        profile_data["email_notification_frequency"] = kwargs.pop(
            "email_notification_frequency", "instant"
        )
        profile_data["timezone"] = kwargs.pop("timezone", "UTC")

        user = User(**kwargs)
        user.set_password(kwargs["password"])
        user.save()

        # Profile creation
        profile_data["user"] = user
        UserProfile.objects.create(**profile_data)

        set_untrusted_client_session_id(user, session_id)
        set_client_undo_redo_action_group_id(user, action_group)
        set_user_websocket_id(user, web_socket_id)

        # add it to a specific workspace if it is given
        if "workspace" in kwargs:
            WorkspaceUser.objects.create(
                workspace=kwargs["workspace"],
                user=user,
                order=0,
                permissions=WORKSPACE_USER_PERMISSION_ADMIN,
            )

        return user

    def create_user_and_token(self, **kwargs) -> Tuple[AbstractUser, str]:
        user = self.create_user(**kwargs)
        token = self.generate_token(user)
        return user, token
