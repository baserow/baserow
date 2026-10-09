from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from baserow_enterprise.agent_builder.models import AgentDefinition


@extend_schema_serializer(component_name="AgentBuilderAgent")
class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentDefinition
        fields = ("id", "agent_builder_id", "name", "order")
        read_only_fields = fields


@extend_schema_serializer(component_name="CreateAgentBuilderAgent")
class CreateAgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentDefinition
        fields = ("name",)


@extend_schema_serializer(component_name="UpdateAgentBuilderAgent")
class UpdateAgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentDefinition
        fields = ("name",)
        extra_kwargs = {"name": {"required": False}}


@extend_schema_serializer(component_name="OrderAgentBuilderAgents")
class OrderAgentsSerializer(serializers.Serializer):
    agent_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="The IDs of the agents in their desired order.",
    )

    def validate_agent_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Agent IDs must be unique.")
        return value
