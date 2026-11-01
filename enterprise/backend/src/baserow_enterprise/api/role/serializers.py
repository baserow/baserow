from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.serializers import NaturalKeyRelatedField
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.registries import (
    application_type_registry,
    object_scope_type_registry,
    subject_type_registry,
)
from baserow_enterprise.exceptions import RoleNotExist, ScopeNotExist, SubjectNotExist
from baserow_enterprise.models import (
    Role,
    RoleAssignment,
    Team,
    WorkspaceScopedInvitation,
)
from baserow_enterprise.role.constants import ALLOWED_SUBJECT_TYPE_BY_PRIORITY
from baserow_enterprise.role.handler import (
    RoleAssignmentHandler,
    get_assignable_scope_type,
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
        return obj.subject_count


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


class EffectiveAccessTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ("id", "name")


class EffectiveAccessSerializer(serializers.Serializer):
    """
    Serializes an `EffectiveAccess`. The teams are limited to the ones whose
    members the requesting user may list, given as `visible_team_ids` in the
    context, while `through_teams` still tells that the role comes from a team.
    """

    subject_type = serializers.SerializerMethodField(
        help_text="The type of the subject: a user or an agent."
    )
    subject_id = serializers.SerializerMethodField(help_text="The subject's id.")
    role = serializers.SerializerMethodField(
        help_text="The uid of the role the subject effectively holds on the scope."
    )
    source_scope_type = serializers.SerializerMethodField(
        help_text="The type of the scope the role comes from: the requested scope "
        "or one above it."
    )
    source_scope_id = serializers.SerializerMethodField(
        help_text="The id of the scope the role comes from."
    )
    through_teams = serializers.SerializerMethodField(
        help_text="Whether the subject holds the role through their teams rather "
        "than themselves."
    )
    teams = serializers.SerializerMethodField(
        help_text="The teams the subject holds the role through, limited to the "
        "teams whose members the requesting user may list."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_subject_type(self, obj):
        return subject_type_registry.get_by_model(obj.subject).type

    @extend_schema_field(OpenApiTypes.INT)
    def get_subject_id(self, obj):
        return obj.subject.id

    @extend_schema_field(OpenApiTypes.STR)
    def get_role(self, obj):
        return obj.role.uid

    @extend_schema_field(OpenApiTypes.STR)
    def get_source_scope_type(self, obj):
        return object_scope_type_registry.get_by_model(obj.source_scope).type

    @extend_schema_field(OpenApiTypes.INT)
    def get_source_scope_id(self, obj):
        return obj.source_scope.id

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_through_teams(self, obj):
        return len(obj.teams) > 0

    @extend_schema_field(EffectiveAccessTeamSerializer(many=True))
    def get_teams(self, obj):
        visible_team_ids = self.context.get("visible_team_ids", set())
        return EffectiveAccessTeamSerializer(
            [team for team in obj.teams if team.id in visible_team_ids], many=True
        ).data


class SubjectRoleAssignmentScopeSerializer(serializers.Serializer):
    scope_type = serializers.SerializerMethodField(
        help_text="The type of the object: an application, a table or a view."
    )
    scope_id = serializers.IntegerField(source="id", help_text="The object's id.")
    name = serializers.CharField(help_text="The object's name.")

    @extend_schema_field(OpenApiTypes.STR)
    def get_scope_type(self, obj):
        return get_assignable_scope_type(obj).type


class SubjectRoleAssignmentSerializer(serializers.Serializer):
    """
    Serializes a `SubjectRoleAssignment`: a role a subject holds on a database,
    table or view, with where that object is and what makes the role inert.
    """

    scope_type = serializers.SerializerMethodField(
        help_text="The type of the object: an application, a table or a view."
    )
    scope_id = serializers.IntegerField(source="scope.id", help_text="The object's id.")
    name = serializers.CharField(source="scope.name", help_text="The object's name.")
    type = serializers.SerializerMethodField(
        help_text="The application type of an application or the view type of a "
        "view, to tell what kind of object it is. Null for a table."
    )
    parents = SubjectRoleAssignmentScopeSerializer(
        source="parent_scopes",
        many=True,
        help_text="The objects the object is in, from the outermost in, without the "
        "workspace.",
    )
    role = serializers.SerializerMethodField(
        help_text="The uid of the role held on the object."
    )
    locked_by = serializers.SerializerMethodField(
        help_text="The workspace, or the application or table the object is in, on "
        "which the subject holds the admin role themselves, which makes this role "
        "have no effect. Null when the role applies."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_scope_type(self, obj):
        return get_assignable_scope_type(obj.scope).type

    @extend_schema_field(OpenApiTypes.STR)
    def get_role(self, obj):
        return RoleAssignmentHandler().get_role_by_id(obj.role_assignment.role_id).uid

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, obj):
        scope_type = get_assignable_scope_type(obj.scope).type
        if scope_type == "application":
            return application_type_registry.get_by_model(obj.scope.specific_class).type
        if scope_type == "database_view":
            return view_type_registry.get_by_model(obj.scope.specific_class).type
        return None

    @extend_schema_field(SubjectRoleAssignmentScopeSerializer(allow_null=True))
    def get_locked_by(self, obj):
        if obj.locked_by is None:
            return None
        return SubjectRoleAssignmentScopeSerializer(obj.locked_by).data


class SubjectRoleAssignmentsQueryParametersSerializer(serializers.Serializer):
    subject_type = serializers.ChoiceField(
        choices=lazy(lambda: ALLOWED_SUBJECT_TYPE_BY_PRIORITY, list)(),
        help_text="The type of the subject: a user, an agent or a team.",
    )
    subject_id = serializers.IntegerField(min_value=1, help_text="The subject's id.")
