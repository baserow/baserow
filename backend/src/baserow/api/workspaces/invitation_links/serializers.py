from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.handler import CoreHandler
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


class InvitationLinkRoleUpgradeSerializer(serializers.Serializer):
    current_permissions = serializers.CharField(
        help_text="The current role of the member."
    )
    permissions = serializers.CharField(
        help_text="The role the member gets by joining through the link."
    )


class PublicWorkspaceInvitationLinkSerializer(serializers.ModelSerializer):
    """
    This serializer is used for showing the link to someone who opens it, so not for
    link management purposes.
    """

    invited_by = serializers.SerializerMethodField()
    workspace = serializers.SerializerMethodField()
    workspace_id = serializers.IntegerField(read_only=True)
    role_upgrade = serializers.SerializerMethodField(
        help_text="Set when the user who opens the link is a member of the workspace "
        "and joining through the link would raise their role."
    )

    class Meta:
        model = WorkspaceInvitationLink
        fields = ("slug", "invited_by", "workspace", "workspace_id", "role_upgrade")

    @extend_schema_field(OpenApiTypes.STR)
    def get_invited_by(self, object):
        return object.created_by.first_name if object.created_by else ""

    @extend_schema_field(OpenApiTypes.STR)
    def get_workspace(self, object):
        return object.workspace.name

    @extend_schema_field(InvitationLinkRoleUpgradeSerializer(allow_null=True))
    def get_role_upgrade(self, object):
        user = self.context.get("user")
        if user is None:
            return None
        current_permissions = CoreHandler().get_permissions_raised_by_invitation_link(
            user, object
        )
        if current_permissions is None:
            return None
        return {
            "current_permissions": current_permissions,
            "permissions": object.permissions,
        }
