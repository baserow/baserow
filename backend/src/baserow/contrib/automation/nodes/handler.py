from typing import Any, Dict, Iterable, Optional

from django.db.models import QuerySet

from baserow.core.db import specific_iterator
from baserow.core.utils import extract_allowed
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.node_types import AutomationNodeType
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.nodes.types import UpdatedAutomationNode


class AutomationNodeHandler:

    allowed_fields = ["previous_node_output"]

    def create_node(self, node_type: AutomationNodeType, **kwargs) -> AutomationNode:
        """
        Create a new automation node.

        :param node_type: The automation node's type.
        :return: The newly created automation node instance.
        """

        allowed_prepared_values = extract_allowed(
            kwargs, node_type.allowed_fields
        )

        node = node_type.model_class(**allowed_prepared_values)
        node.save()

        return node.specific

    def get_nodes(
        self, workflow: AutomationWorkflow, base_queryset: Optional[QuerySet] = None
    ) -> Iterable[AutomationNode]:
        """
        Return all the nodes for a workflow.

        :param workflow: The workflow associated with the nodes.
        :param base_queryset: Optional base queryset to filter the results.
        :return: A list of automation nodes.
        """

        if base_queryset is None:
            base_queryset = self.model.objects

        base_queryset = base_queryset.filter(workflow=workflow)

        return specific_iterator(
            base_queryset,
            per_content_type_queryset_hook=(
                lambda action, queryset: automation_node_type_registry.get_by_model(
                    action
                ).enhance_queryset(queryset)
            ),
        )
    
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
        except AutomationWorkflow.DoesNotExist:
            raise AutomationNodeDoesNotExist()
    
    def update_node(self, node: AutomationNode, **kwargs) -> UpdatedAutomationNode:
        """
        Updates fields of the provided AutomationNode.

        :param workflow: The AutomationNode that should be updated.
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

        return UpdatedAutomationNode(
            node, original_node_values, new_node_values
        )

    def export_prepared_values(self, node: AutomationNode) -> Dict[Any, Any]:
        """
        Return a serializable dict of prepared values for the node attributes.

        It is called by undo/redo ActionHandler to store the values in a way that
        could be restored later.

        :param instance: The node instance to export values for.
        :return: A dict of prepared values.
        """

        return {key: getattr(node, key) for key in self.allowed_fields}