from rest_framework import serializers

from baserow_enterprise.field_permissions.models import FieldPermissionRoleEnum


class UpdateFieldPermissionsRequestSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[
            (FieldPermissionRoleEnum.EDITOR.value, "Editor"),  # default
            (FieldPermissionRoleEnum.BUILDER.value, "Builder"),
            (FieldPermissionRoleEnum.ADMIN.value, "Admin"),
            (FieldPermissionRoleEnum.NOBODY.value, "Nobody"),
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


class UpdateFieldPermissionsResponseSerializer(UpdateFieldPermissionsRequestSerializer):
    field_id = serializers.IntegerField(
        help_text="The ID of the field whose permissions were updated."
    )
    can_write_values = serializers.BooleanField(
        required=False,
        help_text="Whether the user can write values to this field.",
    )
