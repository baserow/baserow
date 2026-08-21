from django.utils.functional import lazy

from rest_framework import serializers

from baserow.core.registries import subject_type_registry
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.api.role.serializers import SubjectField, SubjectTypeField
from baserow_enterprise.field_permissions.models import FieldPermissionsRoleEnum
from baserow_enterprise.teams.subjects import TeamSubjectType


class FieldPermissionSubjectRequestSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField(min_value=1)
    subject_type = serializers.ChoiceField(
        choices=[UserSubjectType.type, TeamSubjectType.type]
    )


class FieldPermissionSubjectResponseSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField(read_only=True)
    subject_type = SubjectTypeField(
        read_only=True,
        choices=lazy(subject_type_registry.get_types, list)(),
    )
    subject = SubjectField(read_only=True)


class CommaSeparatedIntegerListField(serializers.ListField):
    child = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        """Convert a comma-separated query parameter into a validated integer list.

        :param data: The comma-separated string or list value to validate.
        :return: The validated list of integer IDs.
        """

        if isinstance(data, str):
            data = data.split(",") if data else []
        return super().to_internal_value(data)


class FieldPermissionSubjectOptionsRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    size = serializers.IntegerField(
        min_value=1, max_value=100, required=False, default=20
    )
    search = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None
    )
    exclude_user_ids = CommaSeparatedIntegerListField(required=False, default=list)
    exclude_team_ids = CommaSeparatedIntegerListField(required=False, default=list)


class FieldPermissionSubjectOptionResponseSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField(read_only=True)
    subject_type = serializers.ChoiceField(
        read_only=True, choices=[UserSubjectType.type, TeamSubjectType.type]
    )
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True, allow_null=True)
    subject_count = serializers.IntegerField(read_only=True, allow_null=True)


class UpdateFieldPermissionsRequestSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[
            (FieldPermissionsRoleEnum.ADMIN.value, "Admin"),
            (FieldPermissionsRoleEnum.BUILDER.value, "Builder"),
            (FieldPermissionsRoleEnum.EDITOR.value, "Editor"),  # default
            (FieldPermissionsRoleEnum.CUSTOM.value, "Custom"),
            (FieldPermissionsRoleEnum.NOBODY.value, "Nobody"),
        ],
        help_text="The role required to update the data for this field.",
    )
    allow_in_forms = serializers.BooleanField(
        default=False,
        required=False,
        help_text=(
            "Whether to allow this field to be shown in forms. Default is False. "
            "This setting is only relevant if the role is not 'EDITOR'. "
        ),
    )
    subjects = FieldPermissionSubjectRequestSerializer(many=True, required=False)

    def validate(self, attrs):
        """Validate that CUSTOM permissions contain unique subjects.

        :param attrs: The deserialized field-permission request data.
        :return: The validated request data.
        :raises serializers.ValidationError: If non-CUSTOM permissions contain
            subjects or the same subject is included more than once.
        """

        subjects = attrs.get("subjects", [])
        if attrs["role"] != FieldPermissionsRoleEnum.CUSTOM.value and subjects:
            raise serializers.ValidationError(
                {"subjects": "Subjects can only be set when the role is CUSTOM."}
            )

        identifiers = [
            (subject["subject_type"], subject["subject_id"]) for subject in subjects
        ]
        if len(identifiers) != len(set(identifiers)):
            raise serializers.ValidationError(
                {"subjects": "The same subject cannot be included more than once."}
            )
        return attrs


class UpdateFieldPermissionsResponseSerializer(UpdateFieldPermissionsRequestSerializer):
    field_id = serializers.IntegerField(
        help_text="The ID of the field whose permissions were updated."
    )
    can_write_values = serializers.BooleanField(
        required=False,
        help_text="Whether the user can write values to this field.",
    )
    subjects = FieldPermissionSubjectResponseSerializer(many=True, read_only=True)
