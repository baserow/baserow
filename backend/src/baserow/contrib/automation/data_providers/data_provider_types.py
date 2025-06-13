from abc import ABC
from typing import List

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.builder.data_providers.exceptions import (
    DataProviderChunkInvalidException,
)
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
            raise DataProviderChunkInvalidException(message)
        return get_value_at_path(previous_node_results, rest)
