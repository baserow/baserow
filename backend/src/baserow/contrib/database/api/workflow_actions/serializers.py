from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.workflow_actions.serializers import WorkflowActionSerializer
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)


class DatabaseWorkflowActionSerializer(WorkflowActionSerializer):
    """
    Basic database workflow action serializer
    """

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return database_workflow_action_type_registry.get_by_model(
            instance.specific_class
        ).type

    class Meta:
        model = DatabaseWorkflowAction
        fields = ("id", "order", "field_id", "type")

        extra_kwargs = {
            "id": {"read_only": True},
            "field_id": {"read_only": True},
        }


class CreateDatabaseWorkflowActionSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(database_workflow_action_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the workflow action.",
    )

    class Meta:
        model = DatabaseWorkflowAction
        fields = ("id", "type")


class UpdateDatabaseWorkflowActionSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(database_workflow_action_type_registry.get_types, list)(),
        required=False,
        help_text="The type of the workflow action.",
    )

    class Meta:
        model = DatabaseWorkflowAction
        fields = ("type",)


class OrderWorkflowActionsSerializer(serializers.Serializer):
    workflow_action_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="The ids of the workflow actions in the order they should be set.",
    )
