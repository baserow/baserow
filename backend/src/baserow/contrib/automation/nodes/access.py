"""
Which nodes show a user the data of a table they may not see.

A node shows the data of its own table: the table's fields in its schema and
context data, and its rows in its test run data. It also shows the data of the
nodes its formulas read, resolved into its test run data, its run results and
the schemas built from them. A user who may not see the node's table isn't
shown any of it; a user who may see the node's table but not one the node
reads, directly or through other nodes, isn't shown the data built from it.

What a test run data was built from is decided when it is stored: the service
keeps the IDs of the tables of the node and of the nodes it read in
`sample_data_table_ids`. A table that no longer exists counts as one the user may
not see. The formulas of today only decide for test run data stored before the
IDs were kept, as editing a formula or deleting a node doesn't change the data
already built.
"""

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.data_providers.registries import (
    automation_data_provider_type_registry,
)
from baserow.contrib.automation.formula_importer import AutomationFormulaImporter
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.integrations.local_baserow.utils import ServiceTableAccess
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import (
    BaserowFormula,
    BaserowFormulaObject,
    get_parse_tree_for_formula,
)
from baserow.core.formula.parser.parser import convert_string_literal_token_to_string
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.services.models import Service
from baserow.core.utils import to_path

# What can wrap the path of a get() and still be read as a literal.
_WRAPPERS = (
    BaserowFormula.BracketsContext,
    BaserowFormula.LeftWhitespaceOrCommentsContext,
    BaserowFormula.RightWhitespaceOrCommentsContext,
)

# The node of a path as it is written in a literal: `previous_node.5.x` or
# `previous_node[5].x`.
_NODE_PART_RE = re.compile(r"\s*[^.\[\s]+\s*(?:\.([^.\[]*)|\[([^\]]*)\])")


@dataclass
class NodeRead:
    """A get() reading a path of a node."""

    provider: str
    # The node as written in the path, which isn't always an ID.
    node: str
    # The path after the node.
    rest: tuple[str, ...]
    # Where the node is in the formula, when it can be told.
    start: Optional[int] = None
    end: Optional[int] = None


@dataclass
class FormulaReads:
    """The nodes formulas read, and whether some read can't be told."""

    node_ids: set[int] = field(default_factory=set)
    # A get() whose path is computed, like get(concat('previous_node.', 1)), can
    # read any node.
    any_node: bool = False
    paths: list[NodeRead] = field(default_factory=list)


def _literal(expr) -> Optional[BaserowFormula.StringLiteralContext]:
    """The string literal of a get() argument, or None when it is computed."""

    while isinstance(expr, _WRAPPERS):
        expr = expr.expr()
    return expr if isinstance(expr, BaserowFormula.StringLiteralContext) else None


def _node_span(literal, node: str) -> tuple[Optional[int], Optional[int]]:
    """Where the node is in the formula, or None when escapes move it."""

    text = literal.getText()
    path = text[1:-1]
    if convert_string_literal_token_to_string(text, text[0] == "'") != path:
        return None, None
    match = _NODE_PART_RE.match(path)
    if match is None:
        return None, None
    group = 1 if match.group(1) is not None else 2
    raw = match.group(group)
    if raw.strip() != node:
        return None, None
    start = literal.start.start + 1 + match.start(group) + raw.index(node)
    return start, start + len(node)


class NodeReferenceCollector(AutomationFormulaImporter):
    """Collects the nodes the get() calls of a formula read."""

    def __init__(self, reads: FormulaReads):
        super().__init__({})
        self.reads = reads

    def _do_func_import(self, function_argument_expressions, function_name: str):
        for expr in function_argument_expressions:
            expr.accept(self)
        if function_name != "get" or not function_argument_expressions:
            # A get() without a path reads nothing.
            return ""
        literal = _literal(function_argument_expressions[0])
        if literal is None:
            self.reads.any_node = True
            return ""
        text = literal.getText()
        provider, *rest = to_path(
            convert_string_literal_token_to_string(text, text[0] == "'")
        )
        try:
            provider_type = automation_data_provider_type_registry.get(provider)
        except InstanceTypeDoesNotExist:
            return ""
        if not provider_type.reads_node_id or not rest:
            return ""
        node, *rest = rest
        start, end = _node_span(literal, node)
        self.reads.paths.append(NodeRead(provider, node, tuple(rest), start, end))
        try:
            # As the data providers read it.
            self.reads.node_ids.add(int(node))
        except (TypeError, ValueError):
            pass  # Not a node ID, so it reads nothing.
        return ""


def formula_reads(formulas: Iterable[Any], reads: FormulaReads = None) -> FormulaReads:
    """
    The nodes the given formulas read. A formula that can't be read, like one
    imported broken, is taken to read every node.
    """

    reads = reads or FormulaReads()
    for formula in formulas:
        try:
            formula = BaserowFormulaObject.to_formula(formula)
            if formula["mode"] == BASEROW_FORMULA_MODE_RAW or not formula["formula"]:
                continue
            tree = get_parse_tree_for_formula(formula["formula"])
            NodeReferenceCollector(reads).visit(tree)
        except Exception:  # noqa: BLE001 - whatever stops the read, fail closed
            reads.any_node = True
    return reads


def node_reads(node: AutomationNode) -> FormulaReads:
    """
    The nodes the formulas of a node read: those of its service, such as an
    iterator's source or a router's conditions, and those of the node itself, such
    as its retry condition.
    """

    service = node.service.specific
    node = node.specific
    try:
        formulas = [
            *service.get_type().formula_generator(service),
            *node.get_type().formula_generator(node),
        ]
    except Exception:  # noqa: BLE001 - whatever stops the read, fail closed
        return FormulaReads(any_node=True)
    return formula_reads(formulas)


class AutomationNodeAccess:
    """
    What a user may see of nodes, as the module describes. Each table is checked
    once, the nodes of a workflow are read once and the formulas of a node are
    parsed once, and only when the workflow has a table the user may not see, so
    one instance can be shared by every node of a request.
    """

    def __init__(self, user: Optional[AbstractUser], include_trashed: bool = False):
        """
        :param user: The user, or None to hide the data of every table.
        :param include_trashed: Whether the trashed nodes of a workflow can be read
            too, as they can in the results of runs made before they were trashed.
        """

        self.include_trashed = include_trashed
        self.tables = ServiceTableAccess(user)
        self._workflow_nodes: dict[int, dict[int, AutomationNode]] = {}
        self._node_of_service: dict[int, AutomationNode] = {}
        self._reads: dict[int, FormulaReads] = {}
        self._reads_hidden: dict[int, bool] = {}

    def add_nodes(
        self, nodes: Iterable[AutomationNode], all_of_workflow: bool = False
    ) -> "AutomationNodeAccess":
        """
        Adds the nodes that will be checked, so their services can be told apart.

        :param all_of_workflow: Whether the nodes are all the nodes of their
            workflow, with their specific services, so it needn't be read again.
        """

        nodes = list(nodes)
        for node in nodes:
            self._node_of_service[node.service_id] = node
        if all_of_workflow:
            for node in nodes:
                self._workflow_nodes.setdefault(node.workflow_id, {})[node.id] = node
        return self

    def _nodes_of(self, node: AutomationNode) -> dict[int, AutomationNode]:
        return self._nodes_of_workflow(node.workflow)

    def _nodes_of_workflow(self, workflow) -> dict[int, AutomationNode]:
        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        if workflow.id not in self._workflow_nodes:
            base_queryset = (
                AutomationNode.objects_and_trash.all() if self.include_trashed else None
            )
            self._workflow_nodes[workflow.id] = {
                other.id: other
                for other in AutomationNodeHandler().get_nodes(
                    workflow, base_queryset=base_queryset, with_cache=False
                )
            }
        return self._workflow_nodes[workflow.id]

    def node_id_hidden(self, workflow, node_id: int) -> bool:
        """
        Like `node_hidden`, for a node of the workflow known by its ID, read with
        the other nodes of the workflow. A node that isn't found is hidden.
        """

        node = self._nodes_of_workflow(workflow).get(node_id)
        return node is None or self.node_hidden(node)

    def _node_reads(self, node: AutomationNode) -> FormulaReads:
        if node.id not in self._reads:
            self._reads[node.id] = node_reads(node)
        return self._reads[node.id]

    def read_nodes(self, node: AutomationNode) -> list[AutomationNode]:
        """
        The nodes of the workflow the node reads, directly or through other nodes,
        without the node itself.
        """

        nodes = self._nodes_of(node)
        visited = {node.id}
        found, to_visit = [], [node]
        while to_visit:
            reads = self._node_reads(to_visit.pop())
            read_ids = nodes.keys() if reads.any_node else reads.node_ids
            for node_id in read_ids:
                if node_id not in visited and node_id in nodes:
                    visited.add(node_id)
                    found.append(nodes[node_id])
                    to_visit.append(nodes[node_id])
        return found

    def read_table_ids(self, node: AutomationNode) -> set[int]:
        """The tables of the nodes the node reads, directly or not."""

        table_ids = set()
        for other in self.read_nodes(node):
            table_ids |= node_table_ids(other)
        return table_ids

    def node_of_service(self, workflow, service: Service) -> Optional[AutomationNode]:
        """The node of the workflow that has the service."""

        return next(
            (
                node
                for node in self._nodes_of_workflow(workflow).values()
                if node.service_id == service.id
            ),
            None,
        )

    def sample_table_ids(self, node: AutomationNode) -> set[int]:
        """
        The tables the test run data stored now for the node is built from: its
        own, those of the nodes it reads, directly or not, and those their own
        test run data was built from.
        """

        table_ids = node_table_ids(node)
        for other in self.read_nodes(node):
            table_ids |= node_table_ids(other)
            table_ids |= set(other.service.specific.sample_data_table_ids or ())
        return table_ids

    def data_table_ids(self, node: AutomationNode) -> set[int]:
        """
        The tables whose fields the user must be able to list to be shown the
        data of the node: those its test run data was built from, or when they
        weren't kept those of the nodes its formulas read, and its own.
        """

        stored = node.service.specific.sample_data_table_ids
        if stored is None:
            stored = self.read_table_ids(node)
        return set(stored) | node_table_ids(node)

    def _workflow_has_hidden_table(self, node: AutomationNode) -> bool:
        return self.workflow_has_hidden_data(node.workflow)

    def reads_hidden_table(self, node: AutomationNode) -> bool:
        """Whether the node reads a node whose table the user may not see."""

        if node.id not in self._reads_hidden:
            self._reads_hidden[node.id] = self._workflow_has_hidden_table(node) and any(
                not self.tables.allows_table(table_id)
                for table_id in self.read_table_ids(node)
            )
        return self._reads_hidden[node.id]

    def workflow_has_hidden_data(self, workflow) -> bool:
        """Whether a node of the workflow shows data the user may not see."""

        return any(
            not self.tables.allows(service)
            or any(
                not self.tables.allows_table(table_id)
                for table_id in service.sample_data_table_ids or ()
            )
            for service in (
                other.service.specific
                for other in self._nodes_of_workflow(workflow).values()
            )
        )

    def node_hidden(self, node: AutomationNode) -> bool:
        """Whether the node shows the user the data of a table they may not see."""

        return not self.tables.allows(node.service.specific) or self.reads_hidden_table(
            node
        )

    def _node(self, service: Service) -> Optional[AutomationNode]:
        return self._node_of_service.get(service.id)

    def table_allows(self, service: Service) -> bool:
        """Whether the user may see the table of the service."""

        return self.tables.allows(service)

    def data_allows(self, service: Service) -> bool:
        """
        Whether the user may see the data the node of the service shows. When the
        tables its test run data was built from are known, they decide, whatever
        the node reads now. A service whose node wasn't added is only checked for
        its own table.
        """

        stored = service.sample_data_table_ids
        if stored is not None:
            return self.tables.allows(service) and all(
                self.tables.allows_table(table_id) for table_id in stored
            )
        node = self._node(service)
        if node is None:
            return self.tables.allows(service)
        return not self.node_hidden(node)


def node_table_ids(node: AutomationNode) -> set[int]:
    """The tables the service of the node reads or writes."""

    service = node.service.specific
    return service.get_type().get_table_ids(service)


class FixedNodeAccess:
    """Shows or hides the table and the data of every node alike."""

    def __init__(self, table: bool, data: bool):
        self.table = table
        self.data = data

    def table_allows(self, service: Service) -> bool:
        return self.table or not service.get_type().get_table_ids(service)

    def data_allows(self, service: Service) -> bool:
        return self.data


ALLOW_ALL = FixedNodeAccess(table=True, data=True)


def visible_schema(service: Service, access) -> Optional[dict[str, Any]]:
    """
    The schema of a service as the user may see it: none when they may not see
    its table, and without what its test run data adds, like the items of an
    iterator, when they may not see the data the node reads.
    """

    if not access.table_allows(service):
        return None
    if not access.data_allows(service):
        service = copy.copy(service)
        service.sample_data = None
    return service.get_type().generate_schema(service)
