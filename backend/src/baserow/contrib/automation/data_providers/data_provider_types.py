from abc import ABC
from typing import List

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.registries import DataProviderType
from baserow.core.utils import get_value_at_path

SENTINEL = "__no_results__"


class AutomationDataProviderType(DataProviderType, ABC):
    ...


class PreviousNodeProviderType(AutomationDataProviderType):
    type = "previous_node"

    def get_data_chunk(
        self, dispatch_context: AutomationDispatchContext, path: List[str]
    ):
        previous_node_id, *rest = path
        previous_node_results = dispatch_context.previous_nodes_results.get(
            int(previous_node_id), SENTINEL
        )
        if previous_node_results is SENTINEL:
            message = (
                "The previous node id is not present in the dispatch context results"
            )
            raise InvalidFormulaContext(message)
        return get_value_at_path(previous_node_results, rest)

    def import_path(self, path, id_mapping, **kwargs):
        """
        Update the previous node ID of the path.

        :param path: the path part list.
        :param id_mapping: The id_mapping of the process import.
        :return: The updated path.
        """

        previous_node_id, *rest = path

        if "automation_workflow_nodes" in id_mapping:
            try:
                previous_node_id = id_mapping["automation_workflow_nodes"][
                    int(previous_node_id)
                ]
                node = AutomationNodeHandler().get_node(previous_node_id)
            except (KeyError, AutomationNodeDoesNotExist):
                # In the event the `previous_node_id` is not found in the `id_mapping`,
                # or if the previous node does not exist, we return the malformed path.
                return [str(previous_node_id), *rest]

            service_type = node.service.specific.get_type()
            rest = service_type.import_context_path(rest, id_mapping)

        return [str(previous_node_id), *rest]
