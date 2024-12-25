from django.contrib.auth import get_user_model

from rest_framework import serializers
from rest_framework.fields import CharField, EmailField
from rest_framework.serializers import ModelSerializer

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.user.validators import password_validation
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
        )
        extra_kwargs = _USER_ADMIN_SERIALIZER_API_DOC_KWARGS


class UserAdminCreateSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, ModelSerializer
):
    """
    Serializes a request body for creating a new user. Do not use for returning user
    data as the password will be returned also.
    """

    # Max length set to match django user models first_name fields max length
    name = CharField(source="first_name", max_length=150, required=True)
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

    # Max length set to match django user models first_name fields max length
    name = CharField(source="first_name", max_length=150, required=False)
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
    # It's not allowed to impersonate a superuser or staff.
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_superuser=False, is_staff=False)
    )

    class Meta:
        fields = ("user",)
