from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.models import WorkspaceInvitationLink


class WorkspaceInvitationLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceInvitationLink
        fields = (
            "id",
            "workspace",
            "name",
            "slug",
            "permissions",
            "created_on",
        )
        extra_kwargs = {"id": {"read_only": True}}


class CreateWorkspaceInvitationLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceInvitationLink
        fields = ("name", "permissions")
        extra_kwargs = {"permissions": {"required": True}}


class UpdateWorkspaceInvitationLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceInvitationLink
        fields = ("name", "permissions")


class PublicWorkspaceInvitationLinkSerializer(serializers.ModelSerializer):
    """
    This serializer is used for showing the link to someone who opens it, so not for
    link management purposes.
    """

    invited_by = serializers.SerializerMethodField()
    workspace = serializers.SerializerMethodField()
    workspace_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = WorkspaceInvitationLink
        fields = ("slug", "invited_by", "workspace", "workspace_id")

    @extend_schema_field(OpenApiTypes.STR)
    def get_invited_by(self, object):
        return object.created_by.first_name if object.created_by else ""

    @extend_schema_field(OpenApiTypes.STR)
    def get_workspace(self, object):
        return object.workspace.name
