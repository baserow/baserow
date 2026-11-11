from abc import ABC
from typing import List

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.history.exceptions import (
    AutomationWorkflowHistoryNodeResultDoesNotExist,
)
from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.registries import DataProviderType
from baserow.core.utils import get_value_at_path

SENTINEL = "__no_results__"


class AutomationDataProviderType(DataProviderType, ABC): ...


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
            previous_node_result = dispatch_context.get_previous_node_result(
                previous_node
            )
        except AutomationWorkflowHistoryNodeResultDoesNotExist as exc:
            message = (
                "The previous node id is not present in the dispatch context results"
            )
            raise InvalidFormulaContext(message) from exc

        service = previous_node.service.specific

        if service.get_type().returns_list:
            previous_node_result = previous_node_result["results"]
            if len(rest) >= 2:
                prepared_path = [
                    rest[0],
                    *service.get_type().prepare_value_path(service, rest[1:]),
                ]
            else:
                prepared_path = rest
        else:
            prepared_path = service.get_type().prepare_value_path(service, rest)

        return get_value_at_path(previous_node_result, prepared_path)

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
            parent_node_result = dispatch_context.get_previous_node_result(parent_node)
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

        current_item = parent_node_result["results"][current_iteration]
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


class CurrentNodeDataProviderType(AutomationDataProviderType):
    """
    The result of the node being dispatched. Only available while the runner
    evaluates that node's retry condition; everywhere else the node has no
    result yet.
    """

    type = "current_node"

    def get_data_chunk(
        self, dispatch_context: AutomationDispatchContext, path: List[str]
    ):
        node = dispatch_context.current_node
        result = dispatch_context.current_node_result

        if node is None or result is None:
            message = (
                "The current node's result is only available in its retry condition"
            )
            raise InvalidFormulaContext(message)

        service = node.service.specific
        service_type = service.get_type()

        if service_type.returns_list:
            result = result["results"]
            if len(path) >= 2:
                prepared_path = [
                    path[0],
                    *service_type.prepare_value_path(service, path[1:]),
                ]
            else:
                prepared_path = path
        else:
            prepared_path = service_type.prepare_value_path(service, path)

        return get_value_at_path(result, prepared_path)

    def import_path(self, path, id_mapping, **kwargs):
        """
        Remap the service specific part of the path, e.g. the `field_<id>` of
        a database service. The path carries no node id: the node whose formula
        is being imported is passed as `current_node` by the node level formula
        pass of `AutomationNodeHandler.import_nodes()`.

        :param path: the path part list.
        :param id_mapping: The id_mapping of the process import.
        :return: The updated path.
        """

        node = kwargs.get("current_node")
        if node is None:
            return path

        service_type = node.service.get_type()
        return service_type.import_context_path(path, id_mapping)
