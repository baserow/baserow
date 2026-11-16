from typing import Any, Iterable

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
from baserow.contrib.automation.nodes.access import (
    AutomationNodeAccess,
    visible_schema,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.graph.types import GraphPointPosition
from baserow.core.services.models import Service


class AutomationServiceSerializer(ServiceSerializer):
    """
    The service of a node, as the context's `service_table_access` lets the
    reader see it. Its schema and context data name the fields of its table, so
    they are left out when the reader may not see that table. Its sample data
    holds the rows of its table and the values of the nodes it reads, so it is
    left out when the reader may not see one of those tables either, and so is
    what the schema builds from it. Without that context, nothing of a table is
    shown.
    """

    table_accessible = serializers.SerializerMethodField(
        help_text="Whether the reader may see the fields of the table this service "
        "uses. The schema and context data are left out when they may not."
    )

    def _access(self):
        return self.context.get("service_table_access") or AutomationNodeAccess(None)

    def to_representation(self, instance: Service) -> dict[str, Any]:
        data = super().to_representation(instance)
        if not self._access().data_allows(instance.specific):
            # The rows of a test run, and the values of the nodes it reads.
            data["sample_data"] = None
        return data

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_table_accessible(self, instance: Service) -> bool:
        return self._access().table_allows(instance.specific)

    def get_schema(self, instance: Service) -> dict[str, Any] | None:
        return visible_schema(instance.specific, self._access())

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


def node_serializer_context(
    user: AbstractUser | None,
    nodes: Iterable[AutomationNode],
    all_of_workflow: bool = False,
) -> dict[str, Any]:
    """
    The context to serialize nodes for a user with, so the services of the nodes
    only show the tables the user may see, directly or through the nodes they
    read. Without a user, no table is shown.

    :param nodes: The nodes that will be serialized.
    :param all_of_workflow: Whether the nodes are all those of their workflow.
    """

    access = AutomationNodeAccess(user).add_nodes(nodes, all_of_workflow)
    return {"service_table_access": access}


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
