from typing import Any

from django.contrib.auth.models import AbstractUser
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.services.serializers import (
    PolymorphicServiceRequestSerializer,
    PolymorphicServiceSerializer,
    ServiceSerializer,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.local_baserow.utils import ServiceTableAccess
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.graph.types import GraphPointPosition
from baserow.core.services.models import Service


class AutomationServiceSerializer(ServiceSerializer):
    """
    The service of a node. Its schema and context data name the fields of the
    table it uses, which is not always a table the reader may see, so they are
    left out when the context's `service_table_access` says the reader may not.
    """

    table_accessible = serializers.SerializerMethodField(
        help_text="Whether the reader may see the fields of the table this service "
        "uses. The schema and context data are left out when they may not."
    )

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_table_accessible(self, instance: Service) -> bool:
        access = self.context.get("service_table_access")
        return access is None or access.allows(instance.specific)

    def get_schema(self, instance: Service) -> dict[str, Any] | None:
        if not self.get_table_accessible(instance):
            return None
        return super().get_schema(instance)

    def get_context_data(self, instance: Service) -> dict[str, Any] | None:
        if not self.get_table_accessible(instance):
            return None
        return super().get_context_data(instance)

    def get_context_data_schema(self, instance: Service) -> dict[str, Any] | None:
        if not self.get_table_accessible(instance):
            return None
        return super().get_context_data_schema(instance)

    class Meta(ServiceSerializer.Meta):
        fields = ServiceSerializer.Meta.fields + ("table_accessible",)


def node_serializer_context(user: AbstractUser) -> dict[str, Any]:
    """
    The context to serialize nodes for a user with, so the services of the nodes
    only show the tables the user may see.
    """

    return {"service_table_access": ServiceTableAccess(user)}


class AutomationPolymorphicServiceSerializer(PolymorphicServiceSerializer):
    base_class = AutomationServiceSerializer


class AutomationNodeSerializer(serializers.ModelSerializer):
    """Basic automation node serializer."""

    type = serializers.SerializerMethodField(help_text="The automation node type.")
    service = AutomationPolymorphicServiceSerializer(
        help_text="The service associated with this automation node."
    )
    # The model field is a `TextField` subclass, which a `ModelSerializer`
    # would render as a plain string; the formula must be exposed as an object.
    retry_condition = FormulaSerializerField(
        help_text=AutomationNode._meta.get_field("retry_condition").help_text,
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return automation_node_type_registry.get_by_model(instance.specific_class).type

    class Meta:
        model = AutomationNode
        fields = (
            "id",
            "label",
            "on_failure",
            "max_retries",
            "retry_condition",
            "service",
            "workflow",
            "type",
        )

        extra_kwargs = {
            "id": {"read_only": True},
            "workflow_id": {"read_only": True},
            "type": {"read_only": True},
        }


class CreateAutomationNodeSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(automation_node_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the automation node",
    )
    reference_node_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="If provided, creates the node relative to the node with the "
        "given id.",
    )
    position = serializers.ChoiceField(
        choices=GraphPointPosition.choices,
        required=False,
        allow_blank=True,
        help_text="The position of the new node relative to the reference node.",
    )
    output = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The unique ID of the branch this node is an output for.",
    )

    class Meta:
        model = AutomationNode
        fields = (
            "id",
            "type",
            "reference_node_id",
            "position",
            "output",
        )


class UpdateAutomationNodeSerializer(serializers.ModelSerializer):
    service = PolymorphicServiceRequestSerializer(
        required=False, help_text="The service associated with this automation node."
    )
    # The choices of `on_failure` and the `max_retries` come from the model.
    # Trigger node types do not list the error policy fields in their
    # `allowed_fields`, so the handler drops them for triggers after validation.
    retry_condition = FormulaSerializerField(
        help_text=AutomationNode._meta.get_field("retry_condition").help_text,
    )

    class Meta:
        model = AutomationNode
        fields = (
            "label",
            "on_failure",
            "max_retries",
            "retry_condition",
            "service",
        )


class ReplaceAutomationNodeSerializer(serializers.Serializer):
    new_type = serializers.ChoiceField(
        choices=lazy(automation_node_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the new automation node",
    )


class MoveAutomationNodeSerializer(serializers.Serializer):
    reference_node_id = serializers.IntegerField(
        required=False,
        help_text="The reference node.",
    )
    position = serializers.ChoiceField(
        choices=GraphPointPosition.choices,
        required=False,
        allow_blank=True,
        help_text="The new position relative to the reference node.",
    )
    output = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The new output.",
    )
