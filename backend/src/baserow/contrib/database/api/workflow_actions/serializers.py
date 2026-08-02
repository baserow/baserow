from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
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


class DispatchWorkflowActionsSerializer(serializers.Serializer):
    row_id = serializers.IntegerField(
        help_text="The id of the row the button was clicked on."
    )


class DispatchResultSerializer(serializers.Serializer):
    workflow_action_id = serializers.IntegerField(
        help_text="The workflow action this result belongs to."
    )
    status = serializers.CharField(
        help_text=(
            "`completed` when the action finished during this request. Reserved "
            "for `dispatched` when slow actions move behind a job."
        )
    )
    data = serializers.JSONField(
        allow_null=True, help_text="The action's result, if it produced one."
    )


class DispatchWorkflowActionsResponseSerializer(serializers.Serializer):
    results = DispatchResultSerializer(many=True)
    client_actions = serializers.SerializerMethodField(
        help_text=(
            "Actions the browser runs itself, in order, after the server "
            "actions have completed."
        )
    )

    @extend_schema_field(
        DiscriminatorCustomFieldsMappingSerializer(
            database_workflow_action_type_registry,
            DatabaseWorkflowActionSerializer,
            many=True,
        )
    )
    def get_client_actions(self, instance):
        return instance.get("client_actions")
