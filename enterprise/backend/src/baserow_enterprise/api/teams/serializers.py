from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.core.models import WorkspaceInvitationLink
from baserow.core.registries import subject_type_registry
from baserow_enterprise.api.role.serializers import RoleField
from baserow_enterprise.exceptions import RoleNotExist
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.handler import SUPPORTED_SUBJECT_TYPES
from baserow_enterprise.teams.models import Team, TeamSubject, WorkspaceTeamInvitation

__all__ = [
    "TeamSerializer",
    "TeamResponseSerializer",
    "TeamSubjectSerializer",
    "GetTeamsViewParamsSerializer",
    "TeamSubjectResponseSerializer",
    "WorkspaceUserEnterpriseTeamSerializer",
    "TeamInvitationSerializer",
    "CreateTeamInvitationSerializer",
]


class TeamSampleSubjectSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField(help_text="The subject's unique identifier.")
    subject_type = serializers.ChoiceField(
        required=True,
        choices=SUPPORTED_SUBJECT_TYPES,
        help_text="The type of subject who belongs to the team.",
    )
    subject_label = serializers.CharField(
        help_text="The subject's label. Defaults to a user's first name."
    )
    team_subject_id = serializers.IntegerField(
        help_text="The team subject unique identifier."
    )


class TeamSubjectSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.ModelSerializer
):
    subject_type = serializers.ChoiceField(
        required=True,
        choices=SUPPORTED_SUBJECT_TYPES,
        help_text="The type of subject that is being invited.",
    )
    subject_id = serializers.IntegerField(
        required=False, default=None, help_text="The subject's unique identifier."
    )
    subject_user_email = serializers.EmailField(
        required=False, default=None, help_text="The user subject's email address."
    )

    class Meta:
        model = TeamSubject
        fields = ("id", "subject_id", "subject_user_email", "subject_type")
        extra_kwargs = {"id": {"read_only": True}}

    def validate(self, attrs):
        """Reject email lookup when the selected subject type does not support it."""

        subject_user_email = attrs.get("subject_user_email")
        if subject_user_email:
            subject_type = subject_type_registry.get(attrs["subject_type"])
            if not subject_type.supports_lookup_field("email"):
                raise serializers.ValidationError(
                    {
                        "subject_user_email": (
                            "Email lookup is not supported for this subject type."
                        )
                    }
                )
        return attrs


class TeamSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.ModelSerializer
):
    default_role = RoleField(
        model=Role,
        custom_does_not_exist_exception_class=RoleNotExist,
        required=False,
        allow_null=True,
        help_text=(
            "The uid of the role you want to assign to the team in the given "
            "workspace. You can omit this property if you want to remove the role."
        ),
    )
    subjects = TeamSubjectSerializer(
        many=True,
        required=False,
        help_text=(
            "An array of subject ID/type objects to be used during team create and "
            "update. When updating, omit it to keep the members of the team as "
            "they are."
        ),
    )

    class Meta:
        model = Team
        fields = ("name", "default_role", "subjects")


class TeamResponseSerializer(serializers.ModelSerializer):
    default_role = serializers.CharField(
        required=False,
        source="default_role_uid",
        help_text=("The uid of the role this team has in its workspace."),
    )
    subject_count = serializers.IntegerField(
        help_text="The amount of subjects (e.g. users) that are currently assigned to this team."
    )
    subject_sample = TeamSampleSubjectSerializer(
        many=True,
        required=False,
        help_text="A sample, by default 10, of the most recent subjects to join this team.",
    )

    class Meta:
        model = Team
        fields = (
            "id",
            "name",
            "workspace",
            "created_on",
            "updated_on",
            "default_role",
            "subject_count",
            "subject_sample",
        )
        extra_kwargs = {"id": {"read_only": True}}


class TeamListResponseSerializer(TeamResponseSerializer):
    """
    A team in the list of teams, with the number of roles it holds on databases,
    tables and restricted views, given as `role_assignment_counts` in the context.
    """

    role_assignment_count = serializers.SerializerMethodField(
        help_text="Enterprise or advanced only: the number of roles this team holds "
        "on databases, tables and restricted views whose roles the requesting user "
        "may read. Null when roles don't apply to the workspace."
    )

    class Meta(TeamResponseSerializer.Meta):
        fields = (*TeamResponseSerializer.Meta.fields, "role_assignment_count")

    @extend_schema_field(OpenApiTypes.INT)
    def get_role_assignment_count(self, obj):
        return self.context.get("role_assignment_counts", {}).get(obj)


class GetTeamsViewParamsSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    page = serializers.IntegerField(required=False, default=1)
    search = serializers.CharField(required=False, allow_null=True, default=None)
    sorts = serializers.CharField(required=False, allow_null=True, default=None)


class TeamSubjectResponseSerializer(serializers.ModelSerializer):
    subject_type = serializers.SerializerMethodField()

    class Meta:
        model = TeamSubject
        fields = ("id", "subject_id", "subject_type", "team")
        extra_kwargs = {"id": {"read_only": True}}

    def get_subject_type(self, obj: TeamSubject) -> str:
        """
        Returns the TeamSubject's `subject_type` natural key.

        :param obj: The TeamSubject record.
        :return: The subject's content type natural key.
        """

        return obj.subject_type_natural_key


class WorkspaceUserEnterpriseTeamSerializer(serializers.Serializer):
    """
    A serializer for the `WorkspaceUserSerializer.teams` field.
    """

    id = serializers.IntegerField(
        read_only=True, help_text="The unique identifier for this team."
    )
    name = serializers.CharField(
        read_only=True, help_text="The team name that this workspace user belongs to."
    )


class TeamInvitationSerializer(serializers.ModelSerializer):
    """Serializer of a pending invitation that adds a person to a team."""

    email = serializers.EmailField(source="invitation.email", read_only=True)

    class Meta:
        model = WorkspaceTeamInvitation
        fields = ("id", "invitation_id", "email", "team_id", "created_on")
        read_only_fields = fields


class CreateTeamInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(
        help_text="The email address of the person that is invited to the team."
    )
    captcha_token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The captcha token proving the request comes from a person, only "
        "required if a captcha provider is enabled for workspace invitations.",
    )


class TeamInvitationLinkSerializer(serializers.ModelSerializer):
    """
    Serializer of a permanent link that adds people to a team. It has no role,
    because the team gives its own role.
    """

    team_id = serializers.IntegerField(
        source="scope_id", read_only=True, help_text="The team the link adds people to."
    )

    class Meta:
        model = WorkspaceInvitationLink
        fields = ("id", "workspace", "team_id", "name", "slug", "created_on")
        read_only_fields = fields


class CreateTeamInvitationLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceInvitationLink
        fields = ("name",)


class UpdateTeamInvitationLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceInvitationLink
        fields = ("name",)
        extra_kwargs = {"name": {"required": True}}
