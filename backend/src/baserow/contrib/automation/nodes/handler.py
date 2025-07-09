from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Union

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
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
    ReplacedAutomationNode,
    UpdatedAutomationNode,
)
from baserow.core.db import specific_iterator
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.storage import ExportZipFile
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import MirrorDict, extract_allowed


class AutomationNodeHandler:
    allowed_fields = [
        "previous_node",
        "previous_node_id",
        "previous_node_output",
        "service",
    ]

    def get_nodes(
        self,
        workflow: AutomationWorkflow,
        specific: Optional[bool] = True,
        base_queryset: Optional[QuerySet] = None,
    ) -> Union[QuerySet[AutomationNode], Iterable[AutomationNode]]:
        """
        Returns all the nodes, filtered by a workflow.

        :param workflow: The workflow associated with the nodes.
        :param specific: A boolean flag indicating whether to return the specific
            nodes and their services
        :param base_queryset: Optional base queryset to filter the results.
        :return: A queryset or list of automation nodes.
        """

        if base_queryset is None:
            base_queryset = AutomationNode.objects.all()

        nodes = base_queryset.select_related("workflow__automation__workspace").filter(
            workflow=workflow
        )

        if specific:
            nodes = specific_iterator(nodes.select_related("content_type"))
            service_ids = [
                node.service_id for node in nodes if node.service_id is not None
            ]
            specific_services_map = {
                s.id: s
                for s in ServiceHandler().get_services(
                    base_queryset=Service.objects.filter(id__in=service_ids)
                )
            }
            for node in nodes:
                service_id = node.service_id
                if service_id is not None and service_id in specific_services_map:
                    node.service = specific_services_map[service_id]

        return nodes

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
            base_queryset = AutomationNode.objects.all()

        try:
            return (
                base_queryset.select_related("workflow__automation__workspace")
                .get(id=node_id)
                .specific
            )
        except AutomationNode.DoesNotExist:
            raise AutomationNodeDoesNotExist(node_id)

    def create_node(
        self,
        node_type: AutomationNodeType,
        workflow: AutomationWorkflow,
        before: Optional[AutomationNode] = None,
        **kwargs,
    ) -> AutomationNode:
        """
        Create a new automation node.

        :param node_type: The automation node's type.
        :param workflow: The workflow the automation node is associated with.
        :param before: If provided and no order is provided, will place the new node
            before the given node.
        :return: The newly created automation node instance.
        """

        allowed_prepared_values = extract_allowed(
            kwargs, self.allowed_fields + node_type.allowed_fields
        )

        order = kwargs.pop("order", None)
        if before:
            parent_node_id = allowed_prepared_values.get("parent_node_id", None)
            order = AutomationNode.get_unique_order_before_node(before, parent_node_id)
        elif not order:
            order = AutomationNode.get_last_order(workflow)

        allowed_prepared_values["workflow"] = workflow
        node = node_type.model_class(order=order, **allowed_prepared_values)
        node.save()

        return node

    def update_node(self, node: AutomationNode, **kwargs) -> UpdatedAutomationNode:
        """
        Updates fields of the provided AutomationNode.

        :param node: The AutomationNode that should be updated.
        :param kwargs: The fields that should be updated with their
            corresponding values.
        :return: The updated AutomationNode.
        """

        node_type = node.get_type()
        original_node_values = node_type.export_prepared_values(node)

        allowed_values = extract_allowed(kwargs, self.allowed_fields)

        for key, value in allowed_values.items():
            setattr(node, key, value)

        node.save()

        new_node_values = node_type.export_prepared_values(node)
        return UpdatedAutomationNode(
            node=node,
            original_values=original_node_values,
            new_values=new_node_values,
        )

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
        workflow: AutomationWorkflow,
        order: List[int],
        base_qs=None,
    ) -> List[int]:
        """
        Assigns a new order to the nodes in a workflow.

        A base_qs can be provided to pre-filter the nodes affected by this change.

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

    def duplicate_node(self, node: AutomationNode) -> AutomationNode:
        """
        Duplicates an existing AutomationNode instance.

        :param node: The AutomationNode that is being duplicated.
        :raises ValueError: When the provided node is not an instance of
            AutomationNode.
        :return: The duplicated node
        """

        exported_node = self.export_node(node)

        exported_node["order"] = AutomationNode.get_last_order(node.workflow)

        id_mapping = defaultdict(lambda: MirrorDict())
        id_mapping["automation_workflow_nodes"] = MirrorDict()

        new_node_clone = self.import_node(
            node.workflow,
            exported_node,
            id_mapping=id_mapping,
        )

        return new_node_clone

    def replace_node(
        self,
        user: AbstractUser,
        node: AutomationNode,
        new_type: AutomationNodeType,
        **kwargs,
    ) -> ReplacedAutomationNode:
        """
        Replaces the `type` of an existing AutomationNode instance with a new type.

        :param user: The user performing the replacement.
        :param node: The AutomationNode that is being replaced.
        :param new_type: The new AutomationNodeType to replace the existing node with.
        :param kwargs: Additional keyword arguments that will be used to prepare the
            new node's values.
        :return: A ReplacedAutomationNode instance containing the new node and
            information about the original node.
        """

        node_type = node.get_type()
        self.delete_node(user, node)
        prepared_values = new_type.prepare_values(kwargs, user)
        new_node = self.create_node(new_type, node.workflow, **prepared_values)

        return ReplacedAutomationNode(
            node=new_node,
            original_node_id=node.id,
            original_node_type=node_type.type,
        )

    def export_node(
        self,
        node: AutomationNode,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ) -> AutomationNodeDict:
        """
        Serializes the given node.

        :param node: The AutomationNode instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :param cache: A cache dictionary to store intermediate results.
        :return: The serialized version.
        """

        return node.get_type().export_serialized(
            node, files_zip=files_zip, storage=storage, cache=cache
        )

    def import_node(
        self,
        workflow: AutomationWorkflow,
        serialized_node: AutomationNodeDict,
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
        serialized_nodes: List[AutomationNodeDict],
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
        :param cache: A cache dictionary to store intermediate results.
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
        serialized_node: AutomationNodeDict,
        id_mapping: Dict[str, Dict[int, int]],
        *args: Any,
        **kwargs: Any,
    ) -> AutomationNode:
        if "automation_workflow_nodes" not in id_mapping:
            id_mapping["automation_workflow_nodes"] = {}

        node_type = automation_node_type_registry.get(serialized_node["type"])

        node_instance = node_type.import_serialized(
            workflow,
            serialized_node,
            id_mapping,
            *args,
            **kwargs,
        )

        id_mapping["automation_workflow_nodes"][
            serialized_node["id"]
        ] = node_instance.id

        return node_instance
