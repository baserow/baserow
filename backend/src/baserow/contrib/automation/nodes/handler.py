from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Union

from django.core.files.storage import Storage
from django.db.models import QuerySet

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeError,
    AutomationNodeNotInWorkflow,
    AutomationNodeSimulateDispatchError,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import AutomationNodeType
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.types import (
    AutomationNodeDict,
    AutomationNodeDuplication,
    NextAutomationNodeValues,
    UpdatedAutomationNode,
)
from baserow.contrib.automation.workflows.runner import AutomationWorkflowRunner
from baserow.core.cache import local_cache
from baserow.core.db import specific_iterator
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.services.exceptions import UnexpectedDispatchException
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.storage import ExportZipFile
from baserow.core.utils import MirrorDict, extract_allowed


class AutomationNodeHandler:
    allowed_fields = ["label", "service", "previous_node_id", "previous_node_output"]

    def get_nodes(
        self,
        workflow: AutomationWorkflow,
        specific: Optional[bool] = True,
        base_queryset: Optional[QuerySet] = None,
        with_cache: bool = True,
    ) -> Union[QuerySet[AutomationNode], Iterable[AutomationNode]]:
        """
        Returns all the nodes, filtered by a workflow.

        :param workflow: The workflow associated with the nodes.
        :param specific: A boolean flag indicating whether to return the specific
            nodes and their services
        :param base_queryset: Optional base queryset to filter the results.
        :param with_cache: Whether to return a cached value, if available.
        :return: A queryset or list of automation nodes.
        """

        def _get_nodes(base_queryset=base_queryset):
            if base_queryset is None:
                base_queryset = AutomationNode.objects.all()

            nodes = base_queryset.select_related(
                "workflow__automation__workspace"
            ).filter(workflow=workflow)

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

        if with_cache and not base_queryset:
            return local_cache.get(
                f"wa_get_{workflow.id}_nodes_{specific}",
                _get_nodes,
            )
        return _get_nodes()

    def get_next_nodes(
        self,
        workflow,
        node: None | AutomationNode,
        output_uid: str | None = None,
        specific: bool = False,
    ) -> Iterable["AutomationNode"]:
        """
        Returns all nodes which follow the given node in the workflow. A list of nodes
        is returned as there can be multiple nodes that follow this one, for example
        when there are multiple branches in the workflow.

        :param workflow: filter nodes for this workflow.
        :param node: this is the previous not. If null, first nodes are returned.
        :param output_uid: filter nodes only for this output uid.
        :param specific: If True, returns the specific node type.
        """

        queryset = AutomationNode.objects.filter(
            previous_node_id=node.id if node else None
        )

        if output_uid is not None:
            queryset = queryset.filter(previous_node_output=output_uid)

        return self.get_nodes(workflow, base_queryset=queryset, specific=specific)

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

    def update_previous_node(
        self,
        new_previous_node: AutomationNode,
        nodes: List[AutomationNode],
        previous_node_output: Optional[str] = None,
    ):
        """
        Relink all nodes to the given new previous node and ensure that we set the
        previous node output correctly.

        :param new_previous_node: The new previous node.
        :param nodes: The nodes to relink.
        :param previous_node_output: The output of the previous node, if any.
        """

        update_kwargs = {"previous_node": new_previous_node}
        if previous_node_output is not None:
            update_kwargs["previous_node_output"] = previous_node_output

        AutomationNode.objects.filter(id__in=[n.id for n in nodes]).update(
            **update_kwargs
        )

    def update_next_nodes_values(
        self,
        next_node_values: List[NextAutomationNodeValues],
    ):
        """
        Update the next nodes values for a list of nodes.

        :param next_node_values: The new next node values.
        """

        next_node_updates = []
        next_nodes = AutomationNode.objects.filter(
            pk__in=[next_node_value["id"] for next_node_value in next_node_values]
        )
        next_nodes_grouped = {node.id: node for node in next_nodes}
        for next_node_value in next_node_values:
            next_node = next_nodes_grouped.get(next_node_value["id"])
            next_node.previous_node_id = next_node_value["previous_node_id"]
            next_node.previous_node_output = next_node_value["previous_node_output"]
            next_node_updates.append(next_node)
        AutomationNode.objects.bulk_update(
            next_node_updates, ["previous_node_id", "previous_node_output"]
        )

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

        # Are we creating a node as a child of another node?
        parent_node_id = allowed_prepared_values.get("parent_node_id", None)

        node_previous_ids_to_update = []

        # Are we creating a node before another? If we are, the
        # `previous_node_id` and `previous_node_output` fields
        # need to be adjusted.
        if before:
            # We're creating a node before another, and it has an
            # output, so we need to re-use it for this new node.
            if before.previous_node_output:
                allowed_prepared_values[
                    "previous_node_output"
                ] = before.previous_node_output

            # Find any nodes which have a previous node ID and output
            # that match the before node's previous node ID and output.
            node_previous_ids_to_update = list(
                workflow.automation_workflow_nodes.filter(
                    previous_node_id=before.previous_node_id,
                    previous_node_output=before.previous_node_output,
                )
            )

        # If we don't already have a `previous_node_id`...
        if "previous_node_id" not in allowed_prepared_values:
            # Figure out what the previous node ID should be. If we've been given a
            # `before` node, then we'll use its previous node ID. If not, we'll use the
            # last node ID of the workflow, which is the last node in the hierarchy.
            allowed_prepared_values["previous_node_id"] = (
                before.previous_node_id
                if before
                else AutomationWorkflow.get_last_node_id(workflow, parent_node_id)
            )

        order = kwargs.pop("order", None)
        if before:
            order = AutomationNode.get_unique_order_before_node(before, parent_node_id)
        elif not order:
            order = AutomationNode.get_last_order(workflow)

        allowed_prepared_values["workflow"] = workflow
        node = node_type.model_class(order=order, **allowed_prepared_values)
        node.save()

        # If we have `previous_node_id` to update, we need to adjust them.
        if node_previous_ids_to_update:
            self.update_previous_node(node, node_previous_ids_to_update)

        # If we have a `before` node, and it had an output, then
        # we need to clear it as `node` has now claimed it as its output.
        if before and before.previous_node_output:
            before.previous_node_output = ""
            before.save(update_fields=["previous_node_output"])

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

    def duplicate_node(self, source_node: AutomationNode) -> AutomationNodeDuplication:
        """
        Duplicates an existing AutomationNode instance.

        :param source_node: The AutomationNode that is being duplicated.
        :raises ValueError: When the provided node is not an instance of
            AutomationNode.
        :return: The `AutomationNodeDuplication` dataclass containing the source
            node, its next nodes values and the duplicated node.
        """

        exported_node = self.export_node(source_node)

        # Does `node` have any next nodes with no output? If so, we need to ensure
        # their `previous_node_id` are updated to the new duplicated node.
        source_node_next_nodes = list(source_node.get_next_nodes(output_uid=""))
        source_node_next_nodes_values = [
            NextAutomationNodeValues(
                id=nn.id,
                previous_node_id=nn.previous_node_id,
                previous_node_output=nn.previous_node_output,
            )
            for nn in source_node_next_nodes
        ]

        exported_node["order"] = AutomationNode.get_last_order(source_node.workflow)
        # The duplicated node can't have the same output as the source node.
        exported_node["previous_node_output"] = ""
        # The duplicated node will follow `node`.
        exported_node["previous_node_id"] = source_node.id

        id_mapping = defaultdict(lambda: MirrorDict())
        id_mapping["automation_workflow_nodes"] = MirrorDict()

        duplicated_node = self.import_node(
            source_node.workflow,
            exported_node,
            id_mapping=id_mapping,
        )

        # Update the nodes that follow the original node to now follow the new clone.
        self.update_previous_node(duplicated_node, source_node_next_nodes)

        # Get the next nodes without outputs of the duplicated node.
        duplicated_node_next_nodes = list(duplicated_node.get_next_nodes(output_uid=""))
        duplicated_node_next_nodes_values = [
            NextAutomationNodeValues(
                id=nn.id,
                previous_node_id=nn.previous_node_id,
                previous_node_output=nn.previous_node_output,
            )
            for nn in duplicated_node_next_nodes
        ]

        return AutomationNodeDuplication(
            source_node=source_node,
            source_node_next_nodes_values=source_node_next_nodes_values,
            duplicated_node=duplicated_node,
            duplicated_node_next_nodes_values=duplicated_node_next_nodes_values,
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
        node_type = automation_node_type_registry.get(serialized_node["type"])

        node_instance = node_type.import_serialized(
            workflow,
            serialized_node,
            id_mapping,
            *args,
            **kwargs,
        )

        return node_instance

    def simulate_dispatch_node(self, node: AutomationNode) -> AutomationNode:
        """
        Simulates a dispatch of the provided node. This will cause the node's
        `service.sample_data` to be populated.

        :param node: The node to simulate the dispatch for.
        :return: The updated node.
        """

        if node.get_type().is_workflow_trigger:
            node.workflow.simulate_until_node = node
            node.workflow.save()
            return node

        dispatch_context = AutomationDispatchContext(
            node.workflow,
            simulate_until_node=node.specific,
        )

        try:
            AutomationWorkflowRunner().run(node.workflow, dispatch_context)
        except (
            AutomationNodeError,
            UnexpectedDispatchException,
        ) as e:
            raise AutomationNodeSimulateDispatchError(str(e))

        node.refresh_from_db()

        return node
