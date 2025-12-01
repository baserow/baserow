from typing import Any, Dict, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.exceptions import AutomationNodeNotReplaceable
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.types import AutomationNodeDict, NodePositionType
from baserow.contrib.automation.workflows.models import AutomationWorkflow
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
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import ServiceTypeSubClass, service_type_registry
from baserow.core.services.types import DispatchResult
from baserow.core.trash.registries import TrashOperationType


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

    # Whether this node type is a trigger. Triggers start workflows.
    is_workflow_trigger = False

    # Whether this node type is an action.
    # Actions are executed as part of workflows.
    is_workflow_action = False

    is_container = False

    class SerializedDict(AutomationNodeDict):
        ...

    @property
    def allowed_fields(self):
        return super().allowed_fields + [
            "label",
            "service",
        ]

    def before_delete(self, node: AutomationNode) -> None:
        """
        A hook called just before a node is deleted. Can be
        overridden by subclasses to implement specific logic.

        :param node: The node instance to about to be deleted.
        """

    def before_replace(self, node: AutomationNode, new_node_type: Instance) -> None:
        """
        A hook called just before a node is replaced. Can be
        overridden by subclasses to implement specific logic.

        :param node: The node instance to about to be replaced.
        :param new_node_type: The new node type that will
            replace the current one.
        """

        if not node.get_type().is_replaceable_with(new_node_type):
            raise AutomationNodeNotReplaceable(
                "Automation nodes can only be updated with a type of the same "
                "category. Triggers cannot be updated with actions, and vice-versa."
            )

    def before_move(
        self,
        node: AutomationNode,
        reference_node: AutomationNode | None,
        position: NodePositionType,
        output: str,
    ):
        """Called before the node is moved."""

    def before_create(
        self,
        workflow: AutomationWorkflow,
        reference_node: AutomationNode | None,
        position: NodePositionType,
        output: str,
    ):
        """
        A hook called just before a node is created. Can be
        overridden by subclasses to implement specific logic.
        """

    def after_create(self, node: AutomationNode) -> None:
        """
        A hook called just after a node is created. Can be
        overridden by subclasses to implement specific logic.

        :param node: The node instance that was just created.
        """

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
        Responsible for deserializing a property of the node type.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for this property.
        """

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
                # We don't migrate formulas here but later after the node import
                import_export_config=kwargs.get("import_export_config"),
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

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[str, Any]],
        **kwargs,
    ):
        if "automation_edge_outputs" not in id_mapping:
            id_mapping["automation_edge_outputs"] = {}

        return super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            **kwargs,
        )

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: AutomationNode = None,
    ) -> Dict[str, Any]:
        """
        Responsible for preparing the node's service. By default,
        the only step is to pass any `service` data into the service.

        :param values: The full node values to prepare.
        :param user: The user on whose behalf the change is made.
        :param instance: A `AutomationNode` instance.
        :return: The modified node values, prepared.
        """

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        service_type = service_type_registry.get(self.service_type)

        if not instance:
            # If we haven't received a node instance, we're preparing
            # as part of creating a new node. If this happens, we need
            # to create a new service.
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

        if (reference_node_id := values.get("reference_node_id", None)) is not None:
            values["reference_node"] = AutomationNodeHandler().get_node(
                reference_node_id
            )

        return values

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        ...

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


class ReplaceAutomationNodeTrashOperationType(TrashOperationType):
    """
    The replace-automation-node trash operation is used when an automation node is
    replaced with another node type. This operation type exists to ensure that extra
    steps are followed when the node is restored from its trashed state.
    """

    type = "replace_automation_node"

    """
    This trash operation type is 'managed'. We don't want users to interact with
    it in the workspace trash, the system is responsible for it.
    """
    managed = True

    """
    In this trash operation type we don't want to send any created or deleted signals.
    We need to be precise with our realtime signals, so at a strategic time we use
    the `replace` signal instead.
    """
    send_post_restore_created_signal = False
    send_post_trash_deleted_signal = False


automation_node_type_registry = AutomationNodeTypeRegistry()
