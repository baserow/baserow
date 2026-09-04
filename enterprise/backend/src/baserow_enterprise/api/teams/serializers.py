from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow_enterprise.api.role.serializers import RoleField
from baserow_enterprise.exceptions import RoleNotExist
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.handler import SUPPORTED_SUBJECT_TYPES
from baserow_enterprise.teams.models import Team, TeamSubject

__all__ = [
    "TeamSerializer",
    "TeamResponseSerializer",
    "TeamSubjectSerializer",
    "GetTeamsViewParamsSerializer",
    "TeamSubjectResponseSerializer",
    "WorkspaceUserEnterpriseTeamSerializer",
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
        default=[],
        required=False,
        help_text="An array of subject ID/type objects to be used during team create and update.",
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
