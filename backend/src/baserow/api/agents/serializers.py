from copy import deepcopy

from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.validators import no_url_validation
from baserow.core.agents.registries import agent_extension_registry
from baserow.core.models import Agent


class AgentSubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ("id", "name")


class AgentSerializer(serializers.ModelSerializer):
    workspace_id = serializers.IntegerField(source="workspace.id", read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        for extension in agent_extension_registry.get_all():
            fields.update(deepcopy(extension.response_fields))
        return fields

    class Meta:
        model = Agent
        fields = (
            "id",
            "workspace_id",
            "name",
            "role_uid",
            "last_active",
            "created_on",
            "updated_on",
        )


class AgentRequestSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    name = serializers.CharField(max_length=160, validators=[no_url_validation])
    role_uid = serializers.CharField(max_length=32, required=False)

    def get_fields(self):
        fields = super().get_fields()
        for extension in agent_extension_registry.get_all():
            fields.update(deepcopy(extension.request_fields))
        return fields


class UpdateAgentRequestSerializer(AgentRequestSerializer):
    name = serializers.CharField(
        max_length=160, required=False, validators=[no_url_validation]
    )


class AgentListParamsSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1)
    size = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False, allow_null=True, default=None)
    sorts = serializers.CharField(required=False, allow_null=True, default=None)
