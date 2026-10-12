from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.serializers import NaturalKeyRelatedField
from baserow.core.registries import object_scope_type_registry, subject_type_registry
from baserow_enterprise.exceptions import RoleNotExist, ScopeNotExist, SubjectNotExist
from baserow_enterprise.models import (
    Role,
    RoleAssignment,
    Team,
    WorkspaceScopedInvitation,
)


class SubjectTeamSerializer(serializers.ModelSerializer):
    subject_count = serializers.SerializerMethodField(
        help_text="The amount of subjects (e.g. users) that are currently assigned to this team."
    )

    class Meta:
        model = Team
        fields = (
            "id",
            "name",
            "subject_count",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "name": {"read_only": True},
            "subject_count": {"read_only": True},
        }

    @extend_schema_field(OpenApiTypes.INT)
    def get_subject_count(self, obj):
        return obj.subject_count if hasattr(obj, "subject_count") else 0


class SubjectField(serializers.Serializer):
    def to_representation(self, value):
        return subject_type_registry.get_serializer(value).data


class SubjectTypeField(serializers.ChoiceField):
    """
    A field to automatically get the subject ContentType.
    """

    def to_representation(self, value):
        return subject_type_registry.get_by_model(value.model_class()).type

    def to_internal_value(self, data):
        return subject_type_registry.get(data).get_content_type()


class ScopeTypeField(serializers.ChoiceField):
    """
    A field to automatically get the scope ContentType object.
    """

    def to_representation(self, value):
        # Value is a content_type
        scope_type = object_scope_type_registry.get_by_model(value.model_class())
        return scope_type.type

    def to_internal_value(self, data):
        # Data is a scope_type name
        scope_type = object_scope_type_registry.get(data)
        return ContentType.objects.get_for_model(scope_type.model_class)


@extend_schema_field(OpenApiTypes.STR)
class RoleField(NaturalKeyRelatedField):
    def get_queryset(self):
        return super().get_queryset().filter(hidden=False)


class CreateRoleAssignmentSerializer(serializers.Serializer):
    """
    The create role assignment serializer.
    """

    subject_id = serializers.IntegerField(
        min_value=1,
        help_text="The subject ID. A subject is an actor that can do operations.",
    )
    subject_type = SubjectTypeField(
        help_text="The subject type.",
        choices=lazy(subject_type_registry.get_types, list)(),
    )

    role = RoleField(
        model=Role,
        required=True,
        allow_null=True,
        help_text=(
            "The uid of the role you want to assign to the user or team in the given "
            "workspace. You can omit this property if you want to remove the role."
        ),
    )

    scope_id = serializers.IntegerField(
        min_value=1,
        help_text=(
            "The ID of the scope object. The scope object limit the role "
            "assignment to this scope and all its descendants."
        ),
    )
    scope_type = ScopeTypeField(
        help_text="The scope object type.",
        choices=lazy(object_scope_type_registry.get_types, list)(),
    )

    def to_internal_value(self, data):
        """
        Populate the scope and the subject with the actual object.
        """

        try:
            result = super().to_internal_value(data)
        except Role.DoesNotExist:
            raise RoleNotExist()
        # Populate scope and subject with real object
        try:
            result["scope"] = result["scope_type"].get_object_for_this_type(
                id=result["scope_id"]
            )
        except ObjectDoesNotExist:
            raise ScopeNotExist()
        try:
            result["subject"] = result["subject_type"].get_object_for_this_type(
                id=result["subject_id"]
            )
        except ObjectDoesNotExist:
            raise SubjectNotExist()

        return result


class BatchCreateRoleAssignmentSerializer(serializers.Serializer):
    items = CreateRoleAssignmentSerializer(many=True)


class RoleAssignmentSerializer(serializers.ModelSerializer):
    """
    Serializer for RoleAssignment used for response.
    """

    subject = SubjectField()
    subject_type = SubjectTypeField(
        choices=lazy(subject_type_registry.get_types, list)(),
        help_text="The subject type.",
    )
    scope_type = ScopeTypeField(
        help_text=(
            "The type of the scope object. The scope object limit the role "
            "assignment to this scope and all its descendants."
        ),
        choices=lazy(object_scope_type_registry.get_types, list)(),
    )
    role = RoleField(
        model=Role,
        help_text=(
            "The uid of the role assigned to the user or team in the given workspace."
        ),
    )

    class Meta:
        model = RoleAssignment
        fields = (
            "id",
            "role",
            "subject",
            "subject_id",
            "scope_id",
            "subject_type",
            "scope_type",
        )


class OpenApiSubjectField(serializers.Serializer):
    id = serializers.IntegerField()


class OpenApiRoleAssignmentSerializer(RoleAssignmentSerializer):
    """
    Serializer for RoleAssignment used for the Open API spec
    """

    subject = OpenApiSubjectField(
        help_text=f"The structure of the subject field depends on the subject type"
        f"returned and will have additional fields accordingly"
    )


class GetRoleAssignmentsQueryParametersSerializer(serializers.Serializer):
    scope_id = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text=(
            "The ID of the scope object. The scope object limit the role "
            "assignments returned to this scope specifically"
        ),
    )
    scope_type = ScopeTypeField(
        required=False,
        help_text="The scope object type.",
        choices=lazy(object_scope_type_registry.get_types, list)(),
    )

    def to_internal_value(self, data):
        """
        Populate the scope with the actual object.
        """

        if "scope_type" not in data:
            raise serializers.ValidationError({"scope_type": "This field is required."})

        if "scope_id" not in data:
            raise serializers.ValidationError({"scope_id": "This field is required."})

        result = super().to_internal_value(data)
        try:
            # Populate scope and subject with real object
            result["scope"] = result["scope_type"].get_object_for_this_type(
                id=result["scope_id"]
            )
        except ObjectDoesNotExist:
            raise ScopeNotExist()
        return result


class ScopedInvitationSerializer(serializers.ModelSerializer):
    """
    Serializer of a pending invitation that grants a role on one scope, used for
    managing them.
    """

    email = serializers.EmailField(source="invitation.email", read_only=True)
    invitation_id = serializers.IntegerField(read_only=True)
    role = RoleField(
        model=Role,
        help_text="The uid of the role granted on the scope once the invitation is "
        "accepted.",
    )
    scope_type = ScopeTypeField(
        help_text="The scope object type.",
        choices=lazy(object_scope_type_registry.get_types, list)(),
    )

    class Meta:
        model = WorkspaceScopedInvitation
        fields = (
            "id",
            "invitation_id",
            "email",
            "role",
            "scope_id",
            "scope_type",
            "created_on",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "created_on": {"read_only": True},
        }


class CreateScopedInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(
        help_text="The email address of the person that is invited to the scope."
    )
    role = RoleField(
        model=Role,
        required=True,
        help_text="The uid of the role granted on the scope once the invitation is "
        "accepted.",
    )
    scope_id = serializers.IntegerField(
        min_value=1,
        help_text="The ID of the scope object the role is granted on.",
    )
    scope_type = ScopeTypeField(
        help_text="The scope object type.",
        choices=lazy(object_scope_type_registry.get_types, list)(),
    )
    base_url = serializers.URLField(
        help_text="The base URL where the user can publicly accept the invitation. "
        "The accept token is going to be appended to the base_url (base_url + "
        "'/token')."
    )
    captcha_token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The captcha token proving the request comes from a person, only "
        "required if a captcha provider is enabled for workspace invitations.",
    )

    def to_internal_value(self, data):
        """
        Populate the scope with the actual object.
        """

        try:
            result = super().to_internal_value(data)
        except Role.DoesNotExist:
            raise RoleNotExist()
        try:
            result["scope"] = result["scope_type"].get_object_for_this_type(
                id=result["scope_id"]
            )
        except ObjectDoesNotExist:
            raise ScopeNotExist()
        return result


class UpdateScopedInvitationSerializer(serializers.Serializer):
    role = RoleField(
        model=Role,
        required=True,
        help_text="The uid of the role granted on the scope once the invitation is "
        "accepted.",
    )

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Role.DoesNotExist:
            raise RoleNotExist()


class ScopedInvitationTargetSerializer(serializers.ModelSerializer):
    """
    Describes where a scoped invitation leads, for the page that welcomes the invited
    person. The parent ids let the frontend build the route to the object.
    """

    role = RoleField(model=Role, help_text="The uid of the role granted on the scope.")
    scope_type = ScopeTypeField(
        help_text="The scope object type.",
        choices=lazy(object_scope_type_registry.get_types, list)(),
    )
    application_id = serializers.SerializerMethodField(
        help_text="The application the scope belongs to, or is."
    )
    table_id = serializers.SerializerMethodField(
        help_text="The table the scope belongs to, or is. Null for an application."
    )
    view_id = serializers.SerializerMethodField(
        help_text="The view when the scope is a view, null otherwise."
    )

    class Meta:
        model = WorkspaceScopedInvitation
        fields = (
            "id",
            "role",
            "scope_type",
            "scope_id",
            "application_id",
            "table_id",
            "view_id",
        )

    def _get_target_ids(self, obj):
        if not hasattr(obj, "_target_ids"):
            ids = {"application_id": None, "table_id": None, "view_id": None}
            scope = obj.scope
            if scope is not None:
                scope_type_name = object_scope_type_registry.get_by_model(scope).type
                if scope_type_name == "application":
                    ids["application_id"] = scope.id
                elif scope_type_name == "database_table":
                    ids["application_id"] = scope.database_id
                    ids["table_id"] = scope.id
                elif scope_type_name == "database_view":
                    ids["application_id"] = scope.table.database_id
                    ids["table_id"] = scope.table_id
                    ids["view_id"] = scope.id
            obj._target_ids = ids
        return obj._target_ids

    @extend_schema_field(OpenApiTypes.INT)
    def get_application_id(self, obj):
        return self._get_target_ids(obj)["application_id"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_table_id(self, obj):
        return self._get_target_ids(obj)["table_id"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_view_id(self, obj):
        return self._get_target_ids(obj)["view_id"]
