from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.services.serializers import (
    PolymorphicServiceRequestSerializer,
    PolymorphicServiceSerializer,
)
from baserow.contrib.agent.action_tools.data_providers import (
    agent_action_data_provider_type_registry,
)
from baserow.contrib.agent.action_tools.handler import AgentActionHandler
from baserow.contrib.agent.action_tools.inputs import (
    AgentActionInput,
    validate_action_name,
    validate_inputs,
)
from baserow.contrib.agent.models import AgentAction


class ActionFormulaContextType:
    """Action formulas can read declared inputs, not unrelated trigger payloads."""

    data_provider_type_registry = agent_action_data_provider_type_registry


class AgentActionSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    service = PolymorphicServiceSerializer()
    errors = serializers.SerializerMethodField()

    class Meta:
        model = AgentAction
        fields = (
            "id",
            "type",
            "name",
            "description",
            "inputs",
            "enabled",
            "ask_first",
            "service",
            "errors",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance: AgentAction) -> str:
        return instance.service.get_type().type

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_errors(self, instance: AgentAction) -> dict[str, str]:
        return AgentActionHandler().get_configuration_errors(instance)


class AgentActionWriteSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    name = serializers.CharField(required=False, max_length=64, trim_whitespace=False)
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=10000, trim_whitespace=False
    )
    inputs = serializers.ListField(
        child=serializers.DictField(), required=False, max_length=100
    )
    enabled = serializers.BooleanField(required=False)
    ask_first = serializers.BooleanField(required=False)

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        fields["service"] = PolymorphicServiceRequestSerializer(
            default_type_name=self.context.get("service_type_name"),
            required=False,
            partial=True,
        )
        return fields

    def validate_name(self, value: str) -> str:
        return validate_action_name(value)

    def validate_inputs(self, value: list[dict[str, Any]]) -> list[AgentActionInput]:
        return validate_inputs(value)


class CreateAgentActionSerializer(AgentActionWriteSerializer):
    type = serializers.CharField(max_length=255)


class UpdateAgentActionSerializer(AgentActionWriteSerializer):
    pass
