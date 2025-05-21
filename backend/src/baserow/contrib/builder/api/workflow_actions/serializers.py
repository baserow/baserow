from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.workflow_actions.serializers import WorkflowActionSerializer
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)


class BuilderWorkflowActionSerializer(WorkflowActionSerializer):
    """
    Basic builder workflow action serializer
    """

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return builder_workflow_action_type_registry.get_by_model(
            instance.specific_class
        ).type

    class Meta:
        model = BuilderWorkflowAction
        fields = ("id", "order", "element_id", "type", "event")

        extra_kwargs = {
            "id": {"read_only": True},
            "element_id": {"read_only": True},
        }


class CreateBuilderWorkflowActionSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(builder_workflow_action_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the workflow action",
    )
    element_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text="The id of the element the workflow action is associated with",
    )

    class Meta:
        model = BuilderWorkflowAction
        fields = ("id", "element_id", "type", "event")


class UpdateBuilderWorkflowActionsSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(builder_workflow_action_type_registry.get_types, list)(),
        required=False,
        help_text="The type of the workflow action",
    )

    class Meta:
        model = BuilderWorkflowAction
        fields = ("type",)


class OrderWorkflowActionsSerializer(serializers.Serializer):
    workflow_action_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="The ids of the workflow actions in the order they are supposed to be "
        "set in",
    )
    element_id = serializers.IntegerField(
        required=False, help_text="The element the workflow actions belong to"
    )
