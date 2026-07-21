from django.contrib.auth import get_user_model

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import CharField, EmailField
from rest_framework.serializers import ModelSerializer

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.two_factor_auth.serializers import TwoFactorAuthSerializer
from baserow.api.user.validators import name_validation, password_validation
from baserow.core.models import WorkspaceUser

User = get_user_model()


_USER_ADMIN_SERIALIZER_API_DOC_KWARGS = {
    "is_active": {
        "help_text": "Designates whether this user should be treated as active."
        " Set this to false instead of deleting accounts."
    },
    "is_staff": {
        "help_text": "Designates whether this user is an admin and has access to all "
        "workspaces and Baserow's admin areas. "
    },
}


# Raw OpenAPI schema for the ``two_factor_auth`` admin response field. It is
# ``null`` when the user has no provider configured, otherwise the provider
# ``{type, is_enabled}``. A raw dict (instead of ``TwoFactorAuthSerializer``)
# is used so the field can be marked nullable, which drf-spectacular does not
# infer for a serializer-typed SerializerMethodField.
_USER_ADMIN_TWO_FACTOR_AUTH_FIELD_SCHEMA = {
    "type": "object",
    "nullable": True,
    "description": (
        "The user's two factor auth provider state, or null when no provider "
        "is configured."
    ),
    "required": ["type", "is_enabled"],
    "properties": {
        "type": {"type": "string", "readOnly": True},
        "is_enabled": {"type": "boolean", "readOnly": True},
    },
}


class UserAdminWorkspacesSerializer(ModelSerializer):
    id = serializers.IntegerField(source="workspace.id")
    name = serializers.CharField(source="workspace.name")

    class Meta:
        model = WorkspaceUser

        fields = (
            "id",
            "name",
            "permissions",
        )


class UserAdminResponseSerializer(ModelSerializer):
    """
    Serializes the safe user attributes to expose for a response back to the user.
    """

    # Max length set to match django user models first_name fields max length
    name = CharField(source="first_name", max_length=150)
    username = EmailField()
    workspaces = UserAdminWorkspacesSerializer(source="workspaceuser_set", many=True)
    two_factor_auth = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "name",
            "workspaces",
            "last_login",
            "date_joined",
            "is_active",
            "is_staff",
            "two_factor_auth",
        )
        extra_kwargs = _USER_ADMIN_SERIALIZER_API_DOC_KWARGS

    @extend_schema_field(_USER_ADMIN_TWO_FACTOR_AUTH_FIELD_SCHEMA)
    def get_two_factor_auth(self, object):
        try:
            provider = object.two_factor_auth_provider
        except User.two_factor_auth_provider.RelatedObjectDoesNotExist:
            provider = None

        if provider is None:
            return None

        return TwoFactorAuthSerializer(provider).data


class UserAdminCreateSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, ModelSerializer
):
    """
    Serializes a request body for creating a new user. Do not use for returning user
    data as the password will be returned also.
    """

    name = CharField(
        source="first_name",
        min_length=2,
        max_length=60,
        required=True,
        validators=[name_validation],
    )
    username = EmailField(required=True)
    password = CharField(validators=[password_validation], required=True)

    class Meta:
        model = User
        fields = ("username", "name", "is_active", "is_staff", "password")
        extra_kwargs = {
            **_USER_ADMIN_SERIALIZER_API_DOC_KWARGS,
        }


class UserAdminUpdateSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, ModelSerializer
):
    """
    Serializes a request body for updating a given user. Do not use for returning user
    data as the password will be returned also.
    """

    name = CharField(
        source="first_name",
        min_length=2,
        max_length=60,
        required=False,
        validators=[name_validation],
    )
    username = EmailField(required=False)
    password = CharField(validators=[password_validation], required=False)

    class Meta:
        model = User
        fields = ("username", "name", "is_active", "is_staff", "password")
        extra_kwargs = {
            **_USER_ADMIN_SERIALIZER_API_DOC_KWARGS,
        }


class BaserowImpersonateAuthTokenSerializer(serializers.Serializer):
    """
    Serializer used for impersonation.
    """

    User = get_user_model()
    # It's not allowed to impersonate a superuser, staff or deactivated user.
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_superuser=False, is_staff=False, is_active=True)
    )

    class Meta:
        fields = ("user",)
