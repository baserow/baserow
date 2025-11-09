from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Type, Union

from django.core.files.storage import Storage
from django.db.models import QuerySet

from opentelemetry import trace

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.constants import IMPORT_SERIALIZED_IMPORTING
from baserow.contrib.automation.formula_importer import import_formula
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeMisconfiguredService,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    AutomationNodeActionNodeType,
    AutomationNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.types import AutomationNodeDict
from baserow.core.cache import local_cache
from baserow.core.db import specific_iterator
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.storage import ExportZipFile
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.utils import ChildProgressBuilder, MirrorDict, extract_allowed

tracer = trace.get_tracer(__name__)


class AutomationNodeHandler(metaclass=baserow_trace_methods(tracer)):
    allowed_fields = [
        "label",
        "service",
    ]
    allowed_update_fields = [
        "label",
        "service",
    ]

    def _get_node_cache_key(self, workflow, specific):
        return f"wa_get_{workflow.id}_nodes_{specific}"

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
                self._get_node_cache_key(workflow, specific),
                _get_nodes,
            )
        return _get_nodes()

    def invalidate_node_cache(self, workflow):
        """
        Invalidates the node cache. To be used when we add or remove a node from the
        graph.

        :param workflow: The target workflow cache.
        """

        local_cache.delete(self._get_node_cache_key(workflow, True))
        local_cache.delete(self._get_node_cache_key(workflow, False))

    def get_children(self, node: AutomationNode) -> List[AutomationNode]:
        """
        Returns the direct children of the given node.

        :param node: The parent node.
        :return: A list of node instances that are the children of the given node.
        """

        return node.workflow.get_graph().get_children(node)

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
        **kwargs,
    ) -> AutomationNode:
        """
        Create a new automation node.

        :param node_type: The automation node's type.
        :param workflow: The workflow the automation node is associated with.
        :return: The newly created automation node instance.
        """

        allowed_prepared_values = extract_allowed(
            kwargs, self.allowed_fields + node_type.allowed_fields
        )

        node = node_type.model_class.objects.create(
            workflow=workflow, **allowed_prepared_values
        )

        self.invalidate_node_cache(workflow)

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

    def duplicate_node(self, source_node: AutomationNode) -> AutomationNode:
        """
        Duplicates an existing AutomationNode instance.

        :param source_node: The AutomationNode that is being duplicated.
        :raises ValueError: When the provided node is not an instance of
            AutomationNode.
        :return: The duplicated node.
        """

        exported_node = self.export_node(source_node)

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

        self.invalidate_node_cache(duplicated_node.workflow)

        return duplicated_node

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
        previously exported with '.export_node'.

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
        progress: Optional[ChildProgressBuilder] = None,
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
            imported_nodes.append(node_instance)

            if progress:
                progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        # We migrate service formulas here to make sure all nodes are imported before
        # we migrate them
        for imported_node in imported_nodes:
            service = imported_node.service.specific
            updated_models = service.get_type().import_formulas(
                service, id_mapping, import_formula, **kwargs
            )

            [u.save() for u in updated_models]

        return imported_nodes

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
        :param allowed_nodes: if set, only the nodes from the list will be dispatched.
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
                    return

            if children := node.get_children():
                node_data = dispatch_result.data["results"]

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
                f"The node {node.id} is misconfigured and cannot be dispatched. {str(e)}"
            ) from e
