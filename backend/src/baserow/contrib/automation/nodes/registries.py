from typing import Any, Dict, Optional

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.formula_importer import import_formula
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.types import AutomationNodeDict
from baserow.core.integrations.models import Integration
from baserow.core.registry import (
    CustomFieldsRegistryMixin,
    EasyImportExportMixin,
    Instance,
    InstanceWithFormulaMixin,
    ModelInstanceMixin,
    ModelRegistryMixin,
    PublicCustomFieldsInstanceMixin,
    Registry,
)
from baserow.core.services.exceptions import InvalidServiceTypeDispatchSource
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import ServiceTypeSubClass, service_type_registry
from baserow.core.services.types import DispatchResult


class AutomationNodeType(
    PublicCustomFieldsInstanceMixin,
    InstanceWithFormulaMixin,
    EasyImportExportMixin,
    ModelInstanceMixin,
    Instance,
):
    service_type = None
    parent_property_name = "workflow"
    id_mapping_name = "automation_workflow_nodes"

    request_serializer_field_names = ["previous_node_output"]
    request_serializer_field_overrides = {
        "previous_node_output": serializers.CharField(
            required=False,
            default="",
            allow_blank=True,
            help_text="The output of the previous node.",
        ),
    }

    is_workflow_trigger = False
    is_workflow_action = False

    class SerializedDict(AutomationNodeDict):
        service: Dict
        parent_node_id: Optional[int]
        previous_node_id: Optional[int]

    @property
    def allowed_fields(self):
        return super().allowed_fields + [
            "previous_node_output",
            "service",
        ]

    def get_service_type(self) -> Optional[ServiceTypeSubClass]:
        return (
            service_type_registry.get(self.service_type) if self.service_type else None
        )

    def is_replaceable_with(self, other_node_type: "AutomationNodeType") -> bool:
        """
        Determines if this node type can be replaced with another node type.

        :param other_node_type: The other node type to check against.
        :return: True if this node type can be replaced with the other, False otherwise.
        """

        return (
            self.is_workflow_trigger == other_node_type.is_workflow_trigger
            and self.is_workflow_action == other_node_type.is_workflow_action
        )

    def export_prepared_values(self, node: AutomationNode) -> Dict[Any, Any]:
        """
        Return a serializable dict of prepared values for the node attributes.

        It is called by undo/redo ActionHandler to store the values in a way that
        could be restored later.

        :param node: The node instance to export values for.
        :return: A dict of prepared values.
        """

        values = {key: getattr(node, key) for key in self.allowed_fields}
        values["service"] = service_type_registry.get(
            self.service_type
        ).export_prepared_values(node.service.specific)
        values["workflow"] = node.workflow_id
        return values

    def serialize_property(
        self,
        node: AutomationNode,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "order":
            return str(node.order)

        if prop_name == "service":
            service = node.service.specific
            return service.get_type().export_serialized(
                service, files_zip=files_zip, storage=storage, cache=cache
            )

        return super().serialize_property(
            node,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        """
        If the workflow action has a relation to a service, this method will
        map the service's new `integration_id` and call `import_service` on
        the serialized service values.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for this property.
        """

        if prop_name in ["previous_node_id", "parent_node_id"] and value:
            return id_mapping["automation_workflow_nodes"][value]

        if prop_name == "service" and value:
            integration = None
            serialized_service = value
            integration_id = serialized_service.get("integration_id", None)
            if integration_id:
                integration_id = id_mapping["integrations"].get(
                    integration_id, integration_id
                )
                integration = Integration.objects.get(id=integration_id)

            return ServiceHandler().import_service(
                integration,
                serialized_service,
                id_mapping,
                storage=storage,
                cache=cache,
                files_zip=files_zip,
                import_formula=import_formula,
            )
        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: AutomationNode = None,
    ) -> Dict[str, Any]:
        """
        Responsible for preparing the service-based trigger node. By default,
        the only step is to pass any `service` data into the service.

        :param values: The full trigger node values to prepare.
        :param user: The user on whose behalf the change is made.
        :param instance: A `AutomationServiceNode` subclass instance.
        :return: The modified trigger node values, prepared.
        """

        service_type = service_type_registry.get(self.service_type)

        if not instance:
            # If we haven't received a trigger node instance, we're preparing
            # as part of creating a new node. If this happens, we need to create
            # a new service.
            service = ServiceHandler().create_service(service_type)
        else:
            service = instance.service.specific

        # If we received any service values, prepare them.
        service_values = values.pop("service", None) or {}
        prepared_service_values = service_type.prepare_values(
            service_values, user, service
        )

        # Update the service instance with any prepared service values.
        ServiceHandler().update_service(
            service_type, service, **prepared_service_values
        )

        values["service"] = service
        return values

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        ...

    def dispatch(
        self,
        automation_node: AutomationNode,
        dispatch_context: AutomationDispatchContext,
    ):
        raise InvalidServiceTypeDispatchSource("This service cannot be dispatched.")


class AutomationNodeActionNodeType(AutomationNodeType):
    def dispatch(
        self,
        automation_node: AutomationNode,
        dispatch_context: AutomationDispatchContext,
    ) -> DispatchResult:
        return ServiceHandler().dispatch_service(
            automation_node.service.specific, dispatch_context
        )


class AutomationNodeTypeRegistry(
    Registry,
    ModelRegistryMixin,
    CustomFieldsRegistryMixin,
):
    """Contains all registered automation node types."""

    name = "automation_node_type"


automation_node_type_registry = AutomationNodeTypeRegistry()
