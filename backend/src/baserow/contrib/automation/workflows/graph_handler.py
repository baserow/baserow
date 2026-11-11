from typing import Iterable

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.core.graph.handler import BaseGraphHandler


class AutomationWorkflowGraphHandler(BaseGraphHandler):
    """
    The automation workflow graph handler is responsible for managing
    the graph of an automation workflow.
    """

    base_point_class = AutomationNode
    outputs_id_mapping = "automation_edge_outputs"
    instance_id_mapping = "automation_workflow_nodes"
    does_not_exist_exception = AutomationNodeDoesNotExist

    def get_all_points(self) -> Iterable[AutomationNode]:
        return AutomationNodeHandler().get_nodes(self.instance)
