from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.agent.channels.registries import agent_channel_type_registry
from baserow.contrib.agent.models import AgentChannel


class AgentChannelSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField(help_text="The type of the channel.")

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance: AgentChannel) -> str:
        return agent_channel_type_registry.get_for_channel(instance).type

    class Meta:
        model = AgentChannel
        fields = ("id", "type", "enabled")


class CreateAgentChannelSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(agent_channel_type_registry.get_types, list)(),
        help_text="The type of the channel.",
    )

    class Meta:
        model = AgentChannel
        fields = ("type", "enabled")


class UpdateAgentChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentChannel
        fields = ("enabled",)
