from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Type, Union

from django.core.files.storage import Storage
from django.db.models import QuerySet

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeMisconfiguredService,
    AutomationNodeNotInWorkflow,
)
from baserow.contrib.automation.nodes.models import AutomationActionNode, AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    AutomationNodeActionNodeType,
    AutomationNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.types import (
    AutomationNodeDict,
    AutomationNodeDuplication,
    AutomationNodeMove,
    NextAutomationNodeValues,
)
from baserow.core.cache import local_cache
from baserow.core.db import specific_iterator
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.storage import ExportZipFile
from baserow.core.utils import MirrorDict, extract_allowed

from .signals import automation_node_updated


class AutomationNodeHandler:
    allowed_fields = [
        "label",
        "service",
        "previous_node_id",
        "previous_node_output",
        "parent_node_id",
    ]
    allowed_update_fields = [
        "label",
        "service",
    ]

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

    def get_children(self, node, specific=True):
        nodes = self.get_nodes(node.workflow, specific=specific)

        return [
            n
            for n in nodes
            if n.parent_node_id == node.id and n.previous_node_id is None
        ]

    def get_next_nodes(
        self,
        workflow,
        node: None | AutomationNode,
        output_uid: str | None = None,
        parent: None | AutomationNode = None,
        specific: bool = True,
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

        # We benefit from the cache by using that instead of making a new query
        nodes = self.get_nodes(workflow, specific=specific)

        previous_node_id = node.id if node else None
        parent_node_id = (
            node.parent_node_id if node else (parent.id if parent else None)
        )

        return [
            n
            for n in nodes
            if n.previous_node_id == previous_node_id
            and n.parent_node_id == parent_node_id
            and (output_uid is None or n.previous_node_output == output_uid)
        ]

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
    ) -> List[AutomationActionNode]:
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

        updates = []
        for node in nodes:
            for key, value in update_kwargs.items():
                setattr(node, key, value)
            updates.append(node)

        AutomationNode.objects.bulk_update(updates, update_kwargs.keys())

        return updates

    def update_next_nodes_values(
        self,
        next_node_values: List[NextAutomationNodeValues],
    ) -> List[AutomationActionNode]:
        """
        Update the next nodes values for a list of nodes.

        :param next_node_values: The new next node values.
        :return: The updated nodes.
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
        return next_node_updates

    def create_node(
        self,
        node_type: AutomationNodeType,
        workflow: AutomationWorkflow,
        # before: Optional[AutomationNode] = None,
        # parent: Optional[AutomationNode] = None,
        previous_node: Optional[AutomationNode] = None,
        previous_node_output: str = "",
        parent_node: Optional[AutomationNode] = None,
        **kwargs,
    ) -> AutomationNode:
        """
        Create a new automation node.

        :param node_type: The automation node's type.
        :param workflow: The workflow the automation node is associated with.
        :param before: If provided and no order is provided, will place the new node
            before the given node.
        :param before: If provided and no before is provided, will place the new node
            as child of the given parent node.
        :return: The newly created automation node instance.
        """

        allowed_prepared_values = extract_allowed(
            kwargs, self.allowed_fields + node_type.allowed_fields
        )

        if previous_node:
            allowed_prepared_values["previous_node_id"] = previous_node.id
            allowed_prepared_values["parent_node_id"] = previous_node.parent_node_id
            previous_node_to_update = list(
                previous_node.get_next_nodes(output_uid=previous_node_output)
            )
        else:
            # If we don't have a previous node then we add it at the end.
            allowed_prepared_values[
                "previous_node_id"
            ] = AutomationWorkflow.get_last_node_id(
                workflow, parent_node.id if parent_node else None
            )
            previous_node_to_update = []

        if not previous_node and parent_node:
            allowed_prepared_values["parent_node_id"] = parent_node.id

        allowed_prepared_values["previous_node_output"] = previous_node_output

        # Are we creating a node before another? If we are, the
        # `previous_node_id`, `previous_node_output` and `parent_node_id` fields
        # need to be adjusted.
        """if before:
            allowed_prepared_values["previous_node_id"] = before.previous_node_id
            allowed_prepared_values[
                "previous_node_output"
            ] = before.previous_node_output
            allowed_prepared_values["parent_node_id"] = before.parent_node_id
        else:
            allowed_prepared_values[
                "previous_node_id"
            ] = AutomationWorkflow.get_last_node_id(
                workflow, parent.id if parent else None
            )

            allowed_prepared_values["parent_node_id"] = parent.id if parent else None"""

        # for now we are not using the order
        order = AutomationNode.get_last_order(workflow)

        node = node_type.model_class.objects.create(
            workflow=workflow, order=order, **allowed_prepared_values
        )

        # If we have next nodes to update, we need to adjust them after the creation
        if previous_node:
            self.update_previous_node(
                node,
                previous_node_to_update,
                previous_node_output="",
            )

        # If we have a `before` node, and it had an output, then
        # we need to clear it as `node` has now claimed it as its output.
        """if previous_node_output:
            before.previous_node_output = ""
            before.save(update_fields=["previous_node_output"])"""

        return node

    def update_node(self, node: AutomationNode, **kwargs) -> AutomationNode:
        """
        Updates fields of the provided AutomationNode.

        :param node: The AutomationNode that should be updated.
        :param kwargs: The fields that should be updated with their
            corresponding values.
        :return: The updated AutomationNode.
        """

        allowed_values = extract_allowed(kwargs, self.allowed_update_fields)

        for key, value in allowed_values.items():
            setattr(node, key, value)

        node.save()

        return node

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
                parent_node_id=nn.parent_node_id,
            )
            for nn in source_node_next_nodes
        ]

        exported_node["order"] = AutomationNode.get_last_order(source_node.workflow)
        # The duplicated node can't have the same output as the source node.
        exported_node["previous_node_output"] = ""
        # The duplicated node will follow `node`.
        exported_node["previous_node_id"] = source_node.id
        exported_node["parent_node_id"] = source_node.parent_node_id

        id_mapping = defaultdict(lambda: MirrorDict())
        id_mapping["automation_workflow_nodes"] = MirrorDict()

        import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            is_duplicate=True,
            exclude_sensitive_data=False,
        )

        duplicated_node = self.import_node(
            source_node.workflow,
            exported_node,
            id_mapping=id_mapping,
            import_export_config=import_export_config,
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
                parent_node_id=nn.parent_node_id,
            )
            for nn in duplicated_node_next_nodes
        ]

        return AutomationNodeDuplication(
            source_node=source_node,
            source_node_next_nodes_values=source_node_next_nodes_values,
            duplicated_node=duplicated_node,
            duplicated_node_next_nodes_values=duplicated_node_next_nodes_values,
        )

    def move_node(
        self,
        node_to_move: AutomationActionNode,
        new_previous_node: AutomationNode | None,
        new_previous_node_output: Optional[str] = None,
        new_parent_node: AutomationNode | None = None,
    ) -> AutomationNodeMove:
        """
        Moves an action node to be after another node in the same workflow.

        :param node: The action node to move.
        :param after_node: The node to move the action node after.
        :param previous_node_output: If the destination is an output, the output uid.
        :param order: The new order of the node. If not provided, it will be calculated
            to be last of `after_node`.
        :return: The `AutomationNodeMove` dataclass containing the moved node,
            its original previous node values and its new previous node values.
        """

        workflow = node_to_move.workflow

        # Does `node`, in its current position, have any next nodes? If so,
        # we need to ensure their `previous_node_id` are updated to the new
        # previous node of `node`.
        origin_next_nodes = list(node_to_move.get_next_nodes())
        origin_old_next_nodes_values = [
            NextAutomationNodeValues(
                id=nn.id,
                previous_node_id=nn.previous_node_id,
                parent_node_id=nn.parent_node_id,
                previous_node_output=nn.previous_node_output,
            )
            for nn in origin_next_nodes
        ]

        # Keep a list of "next nodes" at the origin and destination which
        # we've updated. The node service will use this list to send a bulk
        # 'automation nodes updated' signal.
        next_node_updates: List[AutomationActionNode] = []

        # Update the nodes that followed `node` to now follow `node`'s previous node.
        # i.e. they all move "up" one step in the workflow.
        updated_origin_next_nodes = self.update_previous_node(
            node_to_move.previous_node,
            origin_next_nodes,
            node_to_move.previous_node_output,
        )
        next_node_updates.extend(updated_origin_next_nodes)

        origin_new_next_nodes_values = [
            NextAutomationNodeValues(
                id=nn.id,
                previous_node_id=nn.previous_node_id,
                parent_node_id=nn.parent_node_id,
                previous_node_output=nn.previous_node_output,
            )
            for nn in updated_origin_next_nodes
        ]

        # Does `after_node` or `parent_node`,
        # have any next nodes? If so, we need to ensure their `previous_node_id`
        # are updated to `node`.
        if new_previous_node is not None:
            destination_next_nodes = list(
                self.get_next_nodes(
                    workflow,
                    new_previous_node,
                    output_uid=new_previous_node_output,
                    parent=new_parent_node,
                )
            )
        else:
            destination_next_nodes = list(new_parent_node.get_children())

        destination_old_next_nodes_values = [
            NextAutomationNodeValues(
                id=nn.id,
                previous_node_id=nn.previous_node_id,
                parent_node_id=nn.parent_node_id,
                previous_node_output=nn.previous_node_output,
            )
            for nn in destination_next_nodes
        ]

        # Store the original `previous_node_{id,output}` and parent_id so we can revert.
        origin_previous_node_id = node_to_move.previous_node_id
        origin_previous_node_output = node_to_move.previous_node_output
        origin_parent_node_id = node_to_move.parent_node_id

        # Set the new position.
        node_to_move.previous_node_id = (
            new_previous_node.id if new_previous_node else None
        )
        node_to_move.previous_node_output = new_previous_node_output or ""
        node_to_move.parent_node_id = new_parent_node.id if new_parent_node else None
        node_to_move.order = (
            AutomationNode.get_unique_order_before_node(new_previous_node)
            if new_previous_node
            else AutomationNode.get_last_order(workflow, new_parent_node)
        )
        node_to_move.save(
            update_fields=[
                "previous_node_id",
                "previous_node_output",
                "parent_node_id",
                "order",
            ]
        )

        # Update the nodes at the destination that their previous node is now `node`.
        updated_destination_next_nodes = self.update_previous_node(
            node_to_move,
            destination_next_nodes,
            previous_node_output="" if new_previous_node_output else None,
        )
        next_node_updates.extend(updated_destination_next_nodes)

        destination_new_next_nodes_values = [
            NextAutomationNodeValues(
                id=nn.id,
                previous_node_id=nn.previous_node_id,
                parent_node_id=nn.parent_node_id,
                previous_node_output=nn.previous_node_output,
            )
            for nn in updated_destination_next_nodes
        ]

        return AutomationNodeMove(
            node=node_to_move,
            next_node_updates=next_node_updates,
            origin_previous_node_id=origin_previous_node_id,
            origin_previous_node_output=origin_previous_node_output,
            origin_parent_node_id=origin_parent_node_id,
            origin_old_next_nodes_values=origin_old_next_nodes_values,
            origin_new_next_nodes_values=origin_new_next_nodes_values,
            destination_previous_node_id=node_to_move.previous_node_id,
            destination_previous_node_output=node_to_move.previous_node_output,
            destination_parent_node_id=node_to_move.parent_node_id,
            destination_old_next_nodes_values=destination_old_next_nodes_values,
            destination_new_next_nodes_values=destination_new_next_nodes_values,
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
        import_export_config: Optional[ImportExportConfig] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AutomationNode:
        node_type = automation_node_type_registry.get(serialized_node["type"])

        node_instance = node_type.import_serialized(
            workflow,
            serialized_node,
            id_mapping,
            import_export_config=import_export_config,
            *args,
            **kwargs,
        )

        return node_instance

    def dispatch_node(
        self,
        node: "AutomationNode",
        dispatch_context: AutomationDispatchContext,
        allowed_nodes=None,
    ):
        """
        Dispatch one node and recursively dispatch the next nodes.

        :param node: The node to start with.
        :param dispatch_context: The context in which the workflow is being dispatched,
            which contains the event payload and other relevant data.
        :param allowed_nodes: if set only the nodes from the list will be dispatched.
        """

        if dispatch_context.simulate_until_node and allowed_nodes is None:
            allowed_nodes = {
                *dispatch_context.simulate_until_node.get_previous_nodes(),
                dispatch_context.simulate_until_node,
            }

        if allowed_nodes is not None and node not in allowed_nodes:
            # Return early as the node is not on the path until the simulated node
            return

        node_type: Type[AutomationNodeActionNodeType] = node.get_type()
        try:
            dispatch_result = node_type.dispatch(node, dispatch_context)
            dispatch_context.after_dispatch(node, dispatch_result)

            # Return early if this is a simulated dispatch
            if until_node := dispatch_context.simulate_until_node:
                if until_node.id == node.id:
                    # sample_data was updated as it's a simulation we should tell to
                    # the frontend
                    node.service.refresh_from_db(fields=["sample_data"])
                    automation_node_updated.send(self, user=None, node=node)
                    return

            if children := node.get_children():
                node_data = (
                    dispatch_result.data
                    if isinstance(dispatch_result.data, list)
                    else [dispatch_result.data]
                )

                if dispatch_context.simulate_until_node:
                    iterations = [0]
                else:
                    iterations = range(len(node_data))

                for index in iterations:
                    sub_dispatch_context = dispatch_context.clone()
                    sub_dispatch_context.set_current_iteration(node, index)

                    # dispatch context build
                    for child in children:
                        self.dispatch_node(
                            child, sub_dispatch_context, allowed_nodes=allowed_nodes
                        )

            next_nodes = node.get_next_nodes(dispatch_result.output_uid)

            for next_node in next_nodes:
                self.dispatch_node(
                    next_node, dispatch_context, allowed_nodes=allowed_nodes
                )
        except ServiceImproperlyConfiguredDispatchException as e:
            raise AutomationNodeMisconfiguredService(
                f"The node {node.id} has a misconfigured service."
            ) from e
