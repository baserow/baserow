from collections import defaultdict
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeNotInWorkflow,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import AutomationNodeType
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.types import (
    AutomationNodeDict,
    UpdatedAutomationNode,
)
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import MirrorDict, extract_allowed


class AutomationNodeHandler:
    allowed_fields = ["previous_node_output"]

    def create_node(
        self, user: AbstractUser, node_type: AutomationNodeType, **kwargs
    ) -> AutomationNode:
        """
        Create a new automation node.

        :param user: The user trying to create the automation node.
        :param node_type: The automation node's type.
        :return: The newly created automation node instance.
        """

        allowed_prepared_values = extract_allowed(
            kwargs, self.allowed_fields + node_type.allowed_fields
        )

        node = node_type.model_class(**allowed_prepared_values)
        node.save()

        return node

    def get_nodes(
        self, workflow: AutomationWorkflow, base_queryset: Optional[QuerySet] = None
    ) -> QuerySet:
        """
        Return all the nodes for a workflow.

        :param workflow: The workflow associated with the nodes.
        :param base_queryset: Optional base queryset to filter the results.
        :return: A list of automation nodes.
        """

        if base_queryset is None:
            base_queryset = AutomationNode.objects.all()

        return base_queryset.filter(workflow=workflow)

    def get_node(
        self, node_id: int, base_queryset: Optional[QuerySet] = None
    ) -> AutomationNode:
        """
        Return an AutomationNode by its ID.

        :param node_id: The ID of the AutomationNode.
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed.
        :raises AutomationNodeDoesNotExist: If the node doesn't exist.
        :return: The model instance of the AutomationNode
        """

        if base_queryset is None:
            base_queryset = AutomationNode.objects

        try:
            return base_queryset.select_related("workflow__automation__workspace").get(
                id=node_id
            )
        except AutomationNode.DoesNotExist:
            raise AutomationNodeDoesNotExist(node_id)

    def update_node(
        self, user: AbstractUser, node: AutomationNode, **kwargs
    ) -> UpdatedAutomationNode:
        """
        Updates fields of the provided AutomationNode.

        :param user: The user trying to update the automation node.
        :param node: The AutomationNode that should be updated.
        :param kwargs: The fields that should be updated with their
            corresponding values.
        :return: The updated AutomationNode.
        """

        original_node_values = self.export_prepared_values(node)

        allowed_values = extract_allowed(kwargs, self.allowed_fields)

        for key, value in allowed_values.items():
            setattr(node, key, value)

        node.save()

        new_node_values = self.export_prepared_values(node)
        updated_node = UpdatedAutomationNode(
            node, original_node_values, new_node_values
        )

        return updated_node

    def export_prepared_values(self, node: AutomationNode) -> Dict[Any, Any]:
        """
        Return a serializable dict of prepared values for the node attributes.

        It is called by undo/redo ActionHandler to store the values in a way that
        could be restored later.

        :param instance: The node instance to export values for.
        :return: A dict of prepared values.
        """

        return {key: getattr(node, key) for key in self.allowed_fields}

    def delete_node(self, user: AbstractUser, node: AutomationNode) -> None:
        """
        Deletes the specified AutomationNode.

        :param user: The user trying to delete the automation node.
        :param node: The AutomationNode that must be deleted.
        """

        automation = node.workflow.automation
        TrashHandler.trash(user, automation.workspace, automation, node)

    def get_nodes_order(self, workflow: AutomationWorkflow) -> List[int]:
        """
        Returns the nodes in the workflow ordered by the order field.

        :param workflow: The workflow that the nodes belong to.
        :return: A list containing the order of the nodes in the workflow.
        """

        return [
            node.id for node in workflow.automation_workflow_nodes.order_by("order")
        ]

    def order_nodes(
        self,
        user: AbstractUser,
        workflow: AutomationWorkflow,
        order: List[int],
        base_qs=None,
    ) -> List[int]:
        """
        Assigns a new order to the nodes in a workflow.

        A base_qs can be provided to pre-filter the nodes affected by this change.

        :param user: The user trying to order the automation nodes.
        :param workflow: The workflow that the nodes belong to.
        :param order: The new order of the nodes.
        :param base_qs: A QS that can have filters already applied.
        :raises AutomationNodeNotInWorkflow: If the node is not part of the
            provided workflow.
        :return: The new order of the nodes.
        """

        if base_qs is None:
            base_qs = AutomationNode.objects.filter(workflow=workflow)

        try:
            full_order = AutomationNode.order_objects(base_qs, order)
        except IdDoesNotExist as error:
            raise AutomationNodeNotInWorkflow(error.not_existing_id)

        return full_order

    def duplicate_node(
        self, user: AbstractUser, node: AutomationNode
    ) -> AutomationNode:
        """
        Duplicates an existing AutomationNode instance.

        :param user: The user trying to duplicate the automation node.
        :param node: The AutomationNode that is being duplicated.
        :raises ValueError: When the provided node is not an instance of
            AutomationNode.
        :return: The duplicated node
        """

        exported_node = self.export_node(node)

        exported_node["order"] = AutomationNode.get_last_order(node.workflow)

        id_mapping = defaultdict(lambda: MirrorDict())
        id_mapping["automation_nodes"] = MirrorDict()

        new_node_clone = self.import_node(
            node.workflow,
            exported_node,
            id_mapping=id_mapping,
        )

        return new_node_clone

    def export_node(
        self,
        node: AutomationNode,
        *args: Any,
        **kwargs: Any,
    ) -> List[AutomationNodeDict]:
        """
        Serializes the given node.

        :param node: The AutomationNode instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :return: The serialized version.
        """

        return AutomationNodeDict(
            id=node.id,
            order=node.order,
            workflow_id=node.workflow.id,
            service_id=node.specific.service.id,
            parent_node_id=node.parent_node.id if node.parent_node else None,
            previous_node_id=node.previous_node.id if node.previous_node else None,
            previous_node_output=node.previous_node_output,
            type=node.get_type().type,
        )

    def import_node(
        self,
        workflow: AutomationWorkflow,
        serialized_node: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        *args,
        **kwargs,
    ) -> AutomationNode:
        """
        Creates an instance of AutomationNode using the serialized version
        previously exported with `.export_node'.

        :param workflow: The workflow instance the new node should
            belong to.
        :param serialized_node: The serialized version of the
            AutomationNode.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :return: the newly created instance.
        """

        return self.import_nodes(
            workflow,
            [serialized_node],
            id_mapping,
            *args,
            **kwargs,
        )[0]

    def import_nodes(
        self,
        workflow: AutomationWorkflow,
        serialized_nodes: List[Dict[str, Any]],
        id_mapping: Dict[str, Dict[int, int]],
        cache: Optional[Dict] = None,
        *args,
        **kwargs,
    ):
        """
        Import multiple nodes at once.

        :param workflow: The workflow instance the new node should
            belong to.
        :param serialized_nodes: The serialized version of the nodes.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :return: the newly created instances.
        """

        if cache is None:
            cache = {}

        imported_nodes = []
        for serialized_node in serialized_nodes:
            node_instance = self.import_node_only(
                workflow,
                serialized_node,
                id_mapping,
                cache=cache,
                *args,
                **kwargs,
            )
            imported_nodes.append([node_instance, serialized_node])

        return [i[0] for i in imported_nodes]

    def import_node_only(
        self,
        workflow: AutomationWorkflow,
        serialized_node: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        *args: Any,
        **kwargs: Any,
    ) -> AutomationNode:
        if "automation_nodes" not in id_mapping:
            id_mapping["automation_nodes"] = {}

        node_type = automation_node_type_registry.get(serialized_node["type"])

        node_instance = node_type.import_serialized(
            workflow,
            serialized_node,
            id_mapping,
            *args,
            **kwargs,
        )

        id_mapping["automation_nodes"][serialized_node["id"]] = node_instance.id

        return node_instance
