"""
Which nodes show a user the data of a table they may not see.
"""

from typing import Iterable, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.formula_importer import AutomationFormulaImporter
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.integrations.local_baserow.utils import ServiceTableAccess
from baserow.core.formula import (
    BaserowFormula,
    BaserowFormulaException,
    BaserowFormulaObject,
    get_parse_tree_for_formula,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.services.models import Service
from baserow.core.utils import to_path

# The data providers whose paths start with the ID of the node they read.
NODE_DATA_PROVIDERS = ("previous_node", "current_iteration")


class NodeReferenceCollector(AutomationFormulaImporter):
    """Collects the IDs of the nodes the get() calls of a formula read."""

    def __init__(self):
        super().__init__({})
        self.node_ids: set[int] = set()

    def _do_func_import(self, function_argument_expressions, function_name: str):
        for expr in function_argument_expressions:
            expr.accept(self)
        if function_name == "get" and isinstance(
            function_argument_expressions[0], BaserowFormula.StringLiteralContext
        ):
            provider, *path = to_path(function_argument_expressions[0].getText()[1:-1])
            if provider in NODE_DATA_PROVIDERS and path and str(path[0]).isdigit():
                self.node_ids.add(int(path[0]))
        return ""


def referenced_node_ids(node: AutomationNode) -> set[int]:
    """
    The IDs of the nodes the formulas of a node read: those of its service, such
    as an iterator's source or a router's conditions, and its retry condition.
    """

    service = node.service.specific
    formulas = list(service.get_type().formula_generator(service))
    formulas.append(node.retry_condition)
    node_ids = set()
    for formula in formulas:
        formula = BaserowFormulaObject.to_formula(formula)
        if formula["mode"] == BASEROW_FORMULA_MODE_RAW or not formula["formula"]:
            continue
        collector = NodeReferenceCollector()
        try:
            collector.visit(get_parse_tree_for_formula(formula["formula"]))
        except (BaserowFormulaException, RecursionError, ValueError):
            continue  # An invalid formula reads nothing.
        node_ids |= collector.node_ids
    return node_ids


class AutomationNodeAccess:
    """
    Whether a user may see what a node outputs. A node shows the fields and rows
    of the table its service uses, and the values of the nodes its formulas read,
    so it is hidden when the user may not see its table or any node it reads is
    hidden. Each table is checked once, and the formulas of a workflow are only
    read when one of its tables is hidden, so one instance can be shared by every
    node of a request.
    """

    def __init__(self, user: Optional[AbstractUser]):
        """
        :param user: The user, or None to hide every node that shows a table.
        """

        self.tables = ServiceTableAccess(user)
        self._nodes: dict[int, dict[int, AutomationNode]] = {}
        self._node_of_service: dict[int, AutomationNode] = {}
        self._any_hidden_table: dict[int, bool] = {}
        self._hidden: dict[int, bool] = {}

    def add_nodes(self, nodes: Iterable[AutomationNode]) -> "AutomationNodeAccess":
        """
        Reads the nodes of the workflows of the given nodes, so their services can
        be told apart. Nodes already read, with their specific services, are used
        as they are.
        """

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        nodes = list(nodes)
        for node in nodes:
            if node.workflow_id not in self._nodes:
                self._add_workflow_nodes(
                    node.workflow_id,
                    AutomationNodeHandler().get_nodes(node.workflow, with_cache=False),
                )
        return self

    def _add_workflow_nodes(self, workflow_id: int, nodes: Iterable[AutomationNode]):
        by_id = {node.id: node for node in nodes}
        self._nodes[workflow_id] = by_id
        for node in by_id.values():
            self._node_of_service[node.service_id] = node

    def node_hidden(self, node: AutomationNode) -> bool:
        """Whether the node shows the user a table they may not see."""

        if node.workflow_id not in self._nodes:
            self.add_nodes([node])
        nodes = self._nodes[node.workflow_id]
        node = nodes.get(node.id, node)
        if not self._has_hidden_table(node.workflow_id):
            return False
        return self._hidden_in(node, nodes, set())

    def _has_hidden_table(self, workflow_id: int) -> bool:
        if workflow_id not in self._any_hidden_table:
            self._any_hidden_table[workflow_id] = any(
                not self.tables.allows(node.service.specific)
                for node in self._nodes[workflow_id].values()
            )
        return self._any_hidden_table[workflow_id]

    def _hidden_in(
        self,
        node: AutomationNode,
        nodes: dict[int, AutomationNode],
        visiting: set[int],
    ) -> bool:
        if node.id in self._hidden:
            return self._hidden[node.id]
        visiting.add(node.id)
        hidden = not self.tables.allows(node.service.specific) or any(
            self._hidden_in(nodes[node_id], nodes, visiting)
            for node_id in referenced_node_ids(node)
            if node_id in nodes and node_id not in visiting
        )
        visiting.discard(node.id)
        self._hidden[node.id] = hidden
        return hidden

    def table_ids(self, node: AutomationNode) -> set[int]:
        """
        The tables whose data the node shows: the table of its service and those
        of the nodes it reads, directly or through other nodes. The node is hidden
        for a user who may not see one of them.
        """

        if node.workflow_id not in self._nodes:
            self.add_nodes([node])
        nodes = self._nodes[node.workflow_id]
        table_ids, visited, to_visit = set(), set(), [nodes.get(node.id, node)]
        while to_visit:
            current = to_visit.pop()
            if current.id in visited:
                continue
            visited.add(current.id)
            table_id = getattr(current.service.specific, "table_id", None)
            if table_id is not None:
                table_ids.add(table_id)
            to_visit.extend(
                nodes[node_id]
                for node_id in referenced_node_ids(current)
                if node_id in nodes
            )
        return table_ids

    def allows(self, service: Service) -> bool:
        """
        Whether the user may see what the node of the service outputs. A service
        whose node wasn't added is only checked for its own table.
        """

        node = self._node_of_service.get(service.id)
        if node is None:
            return self.tables.allows(service)
        return not self.node_hidden(node)
