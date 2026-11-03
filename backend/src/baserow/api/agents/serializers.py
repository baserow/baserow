from copy import deepcopy

from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.validators import no_url_validation
from baserow.core.agents.handler import AgentHandler
from baserow.core.agents.registries import agent_extension_type_registry
from baserow.core.models import User


class AgentSerializer(serializers.ModelSerializer):
    identity_type = serializers.CharField(
        source="profile.identity_type", read_only=True
    )
    workspace_id = serializers.SerializerMethodField()
    name = serializers.CharField(source="first_name", read_only=True)
    role_uid = serializers.SerializerMethodField()
    last_active = serializers.DateTimeField(
        source="profile.last_active", read_only=True
    )
    created_on = serializers.DateTimeField(source="date_joined", read_only=True)

    def get_workspace_id(self, agent):
        return AgentHandler.get_workspace(agent).id

    def get_role_uid(self, agent):
        return AgentHandler.get_role_uid(agent)

    def get_fields(self):
        fields = super().get_fields()
        for extension in agent_extension_type_registry.get_all():
            fields.update(deepcopy(extension.response_fields))
        return fields

    class Meta:
        model = User
        fields = (
            "id",
            "identity_type",
            "workspace_id",
            "name",
            "role_uid",
            "last_active",
            "created_on",
        )


class AgentListSerializer(AgentSerializer):
    """
    An agent of the list of agents, for the API documentation, with the fields the
    agent extensions add to every agent of a list response.
    """

    def get_fields(self):
        fields = super().get_fields()
        for extension in agent_extension_type_registry.get_all():
            fields.update(deepcopy(extension.list_response_fields))
        return fields


class AgentRequestSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    name = serializers.CharField(max_length=150, validators=[no_url_validation])
    role_uid = serializers.CharField(max_length=32, required=False)

    def get_fields(self):
        fields = super().get_fields()
        for extension in agent_extension_type_registry.get_all():
            fields.update(deepcopy(extension.request_fields))
        return fields


class UpdateAgentRequestSerializer(AgentRequestSerializer):
    name = serializers.CharField(
        max_length=150, required=False, validators=[no_url_validation]
    )


class AgentListParamsSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1)
    size = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False, allow_null=True, default=None)
    sorts = serializers.CharField(required=False, allow_null=True, default=None)
