from typing import Iterable, Optional

from django.db.models import QuerySet

from baserow.core.db import specific_iterator
from baserow.core.utils import extract_allowed
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.node_types import AutomationNodeType
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry

class AutomationNodeHandler:

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