from typing import Any, Dict, List, Optional

from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.services.serializers import (
    PolymorphicServiceSerializer,
    ServiceSerializer,
)
from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.api.workflow_actions.serializers import WorkflowActionSerializer
from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.core.handler import CoreHandler
from baserow.core.services.models import Service


class DatabaseWorkflowActionSerializer(WorkflowActionSerializer):
    """
    Basic database workflow action serializer
    """

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance: DatabaseWorkflowAction) -> str:
        return instance.get_type().type

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
    order = serializers.IntegerField(
        help_text="The order the action carries, which two actions can share."
    )
    position = serializers.IntegerField(
        help_text=(
            "Where the action ran in the sequence, counting from one, so the "
            "browser can tell which results a frontend-only action ran after."
        )
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
    field_names = serializers.DictField(
        child=serializers.CharField(),
        help_text=(
            "Maps `field_<id>` to the name the result is keyed by, so a "
            "frontend-only action can resolve a `previous_action` path."
        ),
    )


class DispatchedClientActionSerializer(DatabaseWorkflowActionSerializer):
    """A frontend-only action, with where it ran in the sequence."""

    position = serializers.SerializerMethodField(
        help_text=(
            "Where the action ran in the sequence, counting from one, on the "
            "same scale as a result's."
        )
    )

    @extend_schema_field(OpenApiTypes.INT)
    def get_position(self, instance: DatabaseWorkflowAction) -> int:
        return self.context.get("positions", {}).get(instance.id)

    class Meta(DatabaseWorkflowActionSerializer.Meta):
        fields = DatabaseWorkflowActionSerializer.Meta.fields + ("position",)


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
            DispatchedClientActionSerializer,
            many=True,
        )
    )
    def get_client_actions(self, instance: Dict[str, Any]) -> List[Dict[str, Any]]:
        return instance.get("client_actions")


class DatabaseServiceSerializer(ServiceSerializer):
    """
    A service as a button field's editor sees it. The schema describes the
    table the action writes to, which is not always a table the reader may
    see, so it is only included when they may.
    """

    table_accessible = serializers.SerializerMethodField(
        help_text="Whether the reader may see the table this service writes to. "
        "The schema is left out when they may not."
    )

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_table_accessible(self, instance: Service) -> bool:
        service = instance.specific
        table = getattr(service, "table", None)
        if table is None:
            # Nothing to hide until a table has been chosen.
            return True

        user = self.context.get("user")
        if user is None:
            return False

        return CoreHandler().check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
            raise_permission_exceptions=False,
        )

    def get_schema(self, instance: Service) -> Optional[Dict[str, Any]]:
        if not self.get_table_accessible(instance):
            return None
        return super().get_schema(instance)

    def get_context_data(self, instance: Service) -> Optional[Dict[str, Any]]:
        if not self.get_table_accessible(instance):
            return None
        return super().get_context_data(instance)

    def get_context_data_schema(self, instance: Service) -> Optional[Dict[str, Any]]:
        if not self.get_table_accessible(instance):
            return None
        return super().get_context_data_schema(instance)

    class Meta(ServiceSerializer.Meta):
        fields = ServiceSerializer.Meta.fields + ("table_accessible",)


class DatabasePolymorphicServiceSerializer(PolymorphicServiceSerializer):
    base_class = DatabaseServiceSerializer
