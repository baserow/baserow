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

        previous_node_id = int(previous_node_id)

        try:
            previous_node = AutomationNodeHandler().get_node(previous_node_id)
        except AutomationNodeDoesNotExist as exc:
            message = "The previous node doesn't exist"
            raise InvalidFormulaContext(message) from exc

        try:
            previous_node_results = dispatch_context.previous_nodes_results[
                int(previous_node.id)
            ]
        except KeyError as exc:
            message = (
                "The previous node id is not present in the dispatch context results"
            )
            raise InvalidFormulaContext(message) from exc

        service = previous_node.service.specific

        if service.get_type().returns_list:
            previous_node_results = previous_node_results["results"]
            if len(rest) >= 2:
                prepared_path = [
                    rest[0],
                    *service.get_type().prepare_value_path(service, rest[1:]),
                ]
            else:
                prepared_path = rest
        else:
            prepared_path = service.get_type().prepare_value_path(service, rest)

        return get_value_at_path(previous_node_results, prepared_path)

    def import_path(self, path, id_mapping, **kwargs):
        """
        Update the previous node ID of the path.

        :param path: the path part list.
        :param id_mapping: The id_mapping of the process import.
        :return: The updated path.
        """

        previous_node_id, *rest = path

        try:
            new_node_id = id_mapping["automation_workflow_nodes"][int(previous_node_id)]
            node = AutomationNodeHandler().get_node(new_node_id)
        except (KeyError, AutomationNodeDoesNotExist):
            # In the event the `previous_node_id` is not found in the `id_mapping`,
            # or if the previous node does not exist, we return the malformed path.
            return [str(previous_node_id), *rest]
        else:
            service_type = node.service.get_type()
            rest = service_type.import_context_path(rest, id_mapping)

            return [str(new_node_id), *rest]


class CurrentIterationDataProviderType(AutomationDataProviderType):
    type = "current_iteration"

    def get_data_chunk(
        self, dispatch_context: AutomationDispatchContext, path: List[str]
    ):
        parent_node_id, *rest = path

        parent_node_id = int(parent_node_id)
        try:
            parent_node = AutomationNodeHandler().get_node(parent_node_id)
        except AutomationNodeDoesNotExist as exc:
            message = "The parent node doesn't exist"
            raise InvalidFormulaContext(message) from exc

        try:
            parent_node_results = dispatch_context.previous_nodes_results[
                parent_node.id
            ]
        except KeyError as exc:
            message = (
                "The parent node id is not present in the dispatch context results"
            )
            raise InvalidFormulaContext(message) from exc

        try:
            current_iteration = dispatch_context.current_iterations[parent_node_id]
        except KeyError as exc:
            message = (
                "The current node iteration is not present in the dispatch context"
            )
            raise InvalidFormulaContext(message) from exc

        current_item = parent_node_results["results"][current_iteration]
        data = {"index": current_iteration, "item": current_item}

        return get_value_at_path(data, rest)

    def import_path(self, path, id_mapping, **kwargs):
        """
        Update the parent node ID of the path.

        :param path: the path part list.
        :param id_mapping: The id_mapping of the process import.
        :return: The updated path.
        """

        parent_node_id, *rest = path

        try:
            new_node_id = id_mapping["automation_workflow_nodes"][int(parent_node_id)]
            node = AutomationNodeHandler().get_node(new_node_id)
        except (KeyError, AutomationNodeDoesNotExist):
            # In the event the `previous_node_id` is not found in the `id_mapping`,
            # or if the previous node does not exist, we return the malformed path.
            return [str(parent_node_id), *rest]
        else:
            service_type = node.service.get_type()
            rest = service_type.import_context_path(rest, id_mapping)

            return [str(new_node_id), *rest]
