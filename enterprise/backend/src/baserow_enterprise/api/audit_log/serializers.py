from django.contrib.auth import get_user_model
from django.utils import translation
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.action.registries import action_type_registry
from baserow.core.jobs.registries import job_type_registry
from baserow_enterprise.audit_log.job_types import AuditLogExportJobType
from baserow_enterprise.audit_log.models import AuditLogEntry

User = get_user_model()


def render_user(user_id, user_email):
    return f"{user_email} ({user_id})" if user_id else ""


def render_workspace(workspace_id, workspace_name):
    return f"{workspace_name} ({workspace_id})" if workspace_id else ""


def render_action_type(action_type):
    return action_type_registry.get(action_type).get_short_description()


class AuditLogQueryParamsSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1)
    search = serializers.CharField(required=False, default=None)
    sorts = serializers.CharField(required=False, default=None)
    user_id = serializers.IntegerField(min_value=1, required=False, default=None)
    workspace_id = serializers.IntegerField(min_value=1, required=False, default=None)
    action_type = serializers.ChoiceField(
        choices=lazy(action_type_registry.get_types, list)(),
        default=None,
        required=False,
    )
    from_timestamp = serializers.DateTimeField(required=False, default=None)
    to_timestamp = serializers.DateTimeField(required=False, default=None)


class AuditLogWorkspaceFilterQueryParamsSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(min_value=1, required=False, default=None)


class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    workspace = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    timestamp = serializers.DateTimeField(source="action_timestamp")

    @extend_schema_field(OpenApiTypes.STR)
    def get_user(self, instance):
        return render_user(instance.user_id, instance.user_email)

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return instance.type

    @extend_schema_field(OpenApiTypes.STR)
    def get_description(self, instance):
        return instance.description

    @extend_schema_field(OpenApiTypes.STR)
    def get_workspace(self, instance):
        return render_workspace(instance.workspace_id, instance.workspace_name)

    class Meta:
        model = AuditLogEntry
        fields = (
            "id",
            "action_type",
            "user",
            "workspace",
            "type",
            "description",
            "timestamp",
            "ip_address",
        )
        read_only_fields = fields


class AuditLogUserSerializer(serializers.ModelSerializer):
    value = serializers.CharField(source="email")

    class Meta:
        model = User
        fields = ("id", "value")


class AuditLogActionTypeSerializer(serializers.Serializer):
    id = serializers.ChoiceField(
        choices=lazy(action_type_registry.get_types, list)(),
        source="type",
    )
    value = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_value(self, instance):
        return render_action_type(instance.type)


def serialize_filtered_action_types(user, search=None, exclude_types=None):
    exclude_types = exclude_types or []

    def filter_action_types(action_types, search):
        search_lower = search.lower()
        return [
            action_type
            for action_type in action_types
            if search_lower in action_type["value"].lower()
        ]

    # Since action's type is translated at runtime and there aren't that
    # many, we can fetch them all and filter them in memory to match the
    # search query on the translated value.
    with translation.override(user.profile.language):
        filtered_action_types = [
            action_type
            for action_type in action_type_registry.get_all()
            if action_type.type not in exclude_types
        ]

        action_types = AuditLogActionTypeSerializer(
            filtered_action_types, many=True
        ).data

        if search:
            action_types = filter_action_types(action_types, search)

        return {
            "count": len(action_types),
            "next": None,
            "previous": None,
            "results": sorted(action_types, key=lambda x: x["value"]),
        }


AuditLogExportJobRequestSerializer = job_type_registry.get(
    AuditLogExportJobType.type
).get_serializer_class(
    base_class=serializers.Serializer,
    request_serializer=True,
    meta_ref_name="SingleAuditLogExportJobRequestSerializer",
)

AuditLogExportJobResponseSerializer = job_type_registry.get(
    AuditLogExportJobType.type
).get_serializer_class(
    base_class=serializers.Serializer,
    meta_ref_name="SingleAuditLogExportJobResponseSerializer",
)
