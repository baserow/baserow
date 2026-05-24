from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.models import WorkspaceInvitation


class WorkspaceInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceInvitation
        fields = (
            "id",
            "workspace",
            "email",
            "permissions",
            "created_on",
        )
        extra_kwargs = {"id": {"read_only": True}}


class CreateWorkspaceInvitationSerializer(serializers.ModelSerializer):
    base_url = serializers.URLField(
        help_text="The base URL where the user can publicly accept his invitation."
        "The accept token is going to be appended to the base_url (base_url "
        "'/token')."
    )

    class Meta:
        model = WorkspaceInvitation
        fields = ("email", "permissions", "base_url")


class UpdateWorkspaceInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceInvitation
        fields = ("permissions",)


class UserWorkspaceInvitationSerializer(serializers.ModelSerializer):
    """
    This serializer is used for displaying the invitation to the user that doesn't
    have access to the workspace yet, so not for invitation management purposes.
    """

    invited_by = serializers.SerializerMethodField()
    workspace = serializers.SerializerMethodField()
    email_exists = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceInvitation
        fields = (
            "id",
            "invited_by",
            "workspace",
            "email",
            "created_on",
            "email_exists",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "created_on": {"read_only": True},
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_invited_by(self, object):
        return object.invited_by.first_name

    @extend_schema_field(OpenApiTypes.STR)
    def get_workspace(self, object):
        return object.workspace.name

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_email_exists(self, object):
        return object.email_exists if hasattr(object, "email_exists") else None


class GetWorkspaceInvitationsViewQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, default=None)
    sorts = serializers.CharField(required=False, default=None)
