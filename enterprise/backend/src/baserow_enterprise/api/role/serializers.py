from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.serializers import NaturalKeyRelatedField
from baserow.core.registries import object_scope_type_registry, subject_type_registry
from baserow_enterprise.exceptions import RoleNotExist, ScopeNotExist, SubjectNotExist
from baserow_enterprise.models import Role, RoleAssignment, Team


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
