from typing import Any, Dict

from django.utils.functional import lazy

from drf_spectacular.plumbing import build_array_type, build_basic_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from baserow.api.app_auth_providers.serializers import (
    PolymorphicAppAuthProviderSerializer,
    ReadPolymorphicAppAuthProviderSerializer,
)
from baserow.api.polymorphic import PolymorphicSerializer
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.constants import USER_SOURCE_CLAIM
from baserow.core.user_sources.exceptions import UserSourceDoesNotExist
from baserow.core.user_sources.jwt_token import UserSourceToken
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import user_source_type_registry
from baserow.core.user_sources.service import UserSourceService


class UserSourceRolesSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = UserSource
        fields = ("id", "roles")

    @extend_schema_field(build_array_type(build_basic_type(OpenApiTypes.STR)))
    def get_roles(self, user_source):
        return user_source.get_type().get_roles(user_source.specific)


class UserSourceSerializer(serializers.ModelSerializer):
    """
    Basic user_source serializer mostly for returned values.
    """

    type = serializers.SerializerMethodField(help_text="The type of the user_source.")
    user_count = serializers.SerializerMethodField(
        help_text="The total number of users in the user source."
    )
    user_count_updated_at = serializers.SerializerMethodField(
        help_text="When the last user count took place."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return user_source_type_registry.get_by_model(instance.specific_class).type

    @extend_schema_field(OpenApiTypes.INT)
    def get_user_count(self, instance):
        user_count = instance.get_type().get_user_count(instance)
        return user_count.count if user_count else None

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_user_count_updated_at(self, instance):
        user_count = instance.get_type().get_user_count(instance)
        return user_count.last_updated if user_count else None

    auth_providers = ReadPolymorphicAppAuthProviderSerializer(
        required=False,
        many=True,
        help_text="Auth providers related to this user source.",
    )

    class Meta:
        model = UserSource
        fields = (
            "id",
            "uid",
            "application_id",
            "integration_id",
            "type",
            "name",
            "order",
            "auth_providers",
            "user_count",
            "user_count_updated_at",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "uid": {"read_only": True},
            "application_id": {"read_only": True},
            "auth_providers": {"read_only": True},
            "integration_id": {"read_only": True},
            "type": {"read_only": True},
            "name": {"read_only": True},
            "order": {"read_only": True, "help_text": "Lowest first."},
            "user_count": {"read_only": True},
            "user_count_updated_at": {"read_only": True},
        }


class PolymorphicUserSourceSerializer(PolymorphicSerializer):
    """
    Polymorphic serializer for App Auth providers.
    """

    base_class = UserSourceSerializer
    registry = user_source_type_registry
    request = False


class CreateUserSourceSerializer(serializers.ModelSerializer):
    """
    This serializer allow to set the type of an user_source and the user_source id
    before which we want to insert the new user_source.
    """

    type = serializers.ChoiceField(
        choices=lazy(user_source_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the user_source.",
    )
    before_id = serializers.IntegerField(
        required=False,
        help_text="If provided, creates the user_source before the user_source with "
        "the given id.",
    )
    integration_id = serializers.IntegerField(
        required=True,
        allow_null=False,
        help_text="The related integration id.",
    )

    auth_providers = PolymorphicAppAuthProviderSerializer(
        required=False,
        many=True,
        help_text="Auth providers related to this user source.",
    )

    class Meta:
        model = UserSource
        fields = ("before_id", "type", "name", "integration_id", "auth_providers")
        extra_kwargs = {
            "name": {"required": True},
        }


class UpdateUserSourceSerializer(serializers.ModelSerializer):
    """
    A serializer to update a user source.
    """

    integration_id = serializers.IntegerField(
        required=False,
        allow_null=False,
        help_text="The related integration id.",
    )

    auth_providers = PolymorphicAppAuthProviderSerializer(
        required=False,
        many=True,
        help_text="Auth providers related to this user source.",
    )

    class Meta:
        model = UserSource
        fields = ("name", "integration_id", "auth_providers")
        extra_kwargs = {
            "name": {"required": False},
            "integration_id": {"required": False},
        }


class MoveUserSourceSerializer(serializers.Serializer):
    """
    Serializer used when moving a user source.
    """

    before_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text=(
            "If provided, the user_source is moved before the user_source with this Id. "
            "Otherwise the user_source is placed at the end of the page."
        ),
    )


class UserSourceUserSerializer(serializers.Serializer):
    """
    A serializer used to serialize a UserSourceUser object.
    """

    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    user_source_id = serializers.IntegerField()
    role = serializers.CharField()


class UsersPerUserSourceSerializer(serializers.Serializer):
    """
    The response of the list user source users endpoint.
    """

    users_per_user_sources = serializers.DictField(
        child=UserSourceUserSerializer(many=True),
        help_text="An object keyed by the id of the "
        "user source and the value being the list of users "
        "for this user source.",
    )


class UserSourceTokenObtainSerializer(TokenObtainPairSerializer):
    """
    Returns the JWT token pair when a user try to authenticate using a User source.
    It delegates the authentication to the specified user source.
    """

    username_field = "email"

    def __init__(self, user_source: UserSource, *args, **kwargs) -> None:
        self.user_source = user_source
        super().__init__(*args, **kwargs)

    def validate(self, attrs: Dict[str, Any]) -> Dict[Any, Any]:
        """
        Use the user_source to authenticate the user. It generates the refresh and
        access token used by the frontend to authenticate the following queries.
        """

        authenticate_kwargs = {
            "email": attrs["email"],
            "password": attrs["password"],
        }
        try:
            authenticate_kwargs["request"] = self.context["request"]
        except KeyError:
            pass

        try:
            user = self.user_source.get_type().authenticate(
                self.user_source, **authenticate_kwargs
            )
        except UserNotFound as exc:
            raise exceptions.AuthenticationFailed(
                "User not found", code="user_not_found"
            ) from exc

        refresh = user.get_refresh_token()

        return {
            "refresh_token": str(refresh),
            "access_token": str(refresh.access_token),
        }


class UserSourceForceTokenObtainSerializer(serializers.Serializer):
    """
    Returns the JWT for the given user_id. It sort of force the authentication without
    credential. That way it's possible to impersonate any user source user. Useful
    if you want to check how an application looks like from the user perspective.
    """

    user_id = serializers.IntegerField()

    def __init__(self, user_source, *args, **kwargs) -> None:
        self.user_source = user_source
        super().__init__(*args, **kwargs)

    def validate(self, attrs: Dict[str, Any]) -> Dict[Any, Any]:
        try:
            user = self.user_source.get_type().get_user(
                self.user_source, user_id=attrs["user_id"]
            )
        except UserNotFound as exc:
            raise exceptions.AuthenticationFailed(
                "User not found", code="user_not_found"
            ) from exc

        refresh = user.get_refresh_token()

        return {
            "refresh_token": str(refresh),
            "access_token": str(refresh.access_token),
        }


class TokenRefreshSerializer(serializers.Serializer):
    """
    Check the refresh token is still valid and if so return a new access token.
    If `ROTATE_REFRESH_TOKENS` then a new refresh token is also returned.
    """

    refresh_token = serializers.CharField()
    access_token = serializers.CharField(read_only=True)
    token_class = UserSourceToken

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, str]:
        try:
            refresh = self.token_class(attrs["refresh_token"])
            user_source_uid = refresh[USER_SOURCE_CLAIM]
            user_id = refresh[jwt_settings.USER_ID_CLAIM]
        except (KeyError, TokenError) as exc:
            raise InvalidToken("The token is invalid or expired") from exc

        try:
            # Check if the user source still exists
            user_source = (
                UserSourceService()
                .get_user_source_by_uid(
                    self.context["user"], user_source_uid, for_authentication=True
                )
                .specific
            )
        except UserSourceDoesNotExist as exc:
            raise InvalidToken("Missing data source") from exc

        try:
            user = user_source.get_type().get_user(user_source, user_id=user_id)
        except UserNotFound as exc:
            raise InvalidToken("User doesn't exist anymore") from exc

        refresh, updated = user.update_refresh_token(refresh)

        data = {"access_token": str(refresh.access_token)}

        if jwt_settings.ROTATE_REFRESH_TOKENS:
            if jwt_settings.BLACKLIST_AFTER_ROTATION:
                refresh.blacklist()

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()

            data["refresh_token"] = str(refresh)
        elif updated:
            data["refresh_token"] = str(refresh)

        return data
