from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.workspaces.invitations.registries import invitation_data_registry
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


def get_workspace_invitation_with_data_serializer():
    """
    Returns a serializer for the `WorkspaceInvitation` model that also documents
    the data added by every type registered in the `InvitationDataRegistry`. It's
    dynamically generated, because the types are registered by plugins.
    """

    attrs = {
        data_type.type: data_type.get_serializer_field()
        for data_type in invitation_data_registry.get_all()
    }

    class Meta(WorkspaceInvitationSerializer.Meta):
        fields = WorkspaceInvitationSerializer.Meta.fields + tuple(attrs.keys())

    attrs["Meta"] = Meta

    return type(
        "WorkspaceInvitationWithDataSerializer",
        (WorkspaceInvitationSerializer,),
        attrs,
    )


class CreateWorkspaceInvitationSerializer(serializers.ModelSerializer):
    captcha_token = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        help_text="The captcha response token, required when captcha is enabled.",
    )

    class Meta:
        model = WorkspaceInvitation
        fields = ("email", "permissions", "captcha_token")


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
    workspace_id = serializers.IntegerField(read_only=True)
    email_exists = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceInvitation
        fields = (
            "id",
            "invited_by",
            "workspace",
            "workspace_id",
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


class AcceptWorkspaceInvitationSerializer(serializers.Serializer):
    token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The token from the invitation email. Required when the email "
        "address of the user is not verified.",
    )


class GetWorkspaceInvitationsViewQuerySerializer(serializers.Serializer):
    search = serializers.CharField(required=False, default=None)
    sorts = serializers.CharField(required=False, default=None)
