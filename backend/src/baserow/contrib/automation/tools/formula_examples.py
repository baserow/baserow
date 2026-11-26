"""Build formula example data from visible workflow outputs, without calling a model."""

from typing import Any

from baserow.contrib.automation.nodes.access import AutomationNodeAccess, visible_schema
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.tools import nodes as shared_nodes
from baserow.core.tools.formula_utils import (
    BaseFormulaContext,
    create_example_from_json_schema,
    minimize_json_schema,
)


class AssistantFormulaContext(BaseFormulaContext):
    """
    Automation-specific formula context.

    Wraps node data in the ``{"previous_node": {...}}`` structure expected
    by automation formula ``get()`` paths.
    """

    def add_node_context(
        self,
        node_id: int | str,
        node_context: dict[str, Any],
        context_metadata: dict[str, dict[str, str]] | None = None,
    ):
        """Add a node's output values to the formula context."""
        self.add_context(str(node_id), node_context, context_metadata)

    def get_formula_context(self) -> dict[str, Any]:
        """Return context wrapped in ``previous_node`` for automation formulas."""
        return {"previous_node": self.context}

    def __getitem__(self, key) -> Any:
        """Resolve paths like ``previous_node.1.0.field_name``."""
        return self._resolve_path(key, "previous_node")


class WorkflowExamples:
    """
    The example data of a workflow's nodes for the generator, read once per
    workflow however many of its nodes are repaired.
    """

    def __init__(self, user, refs: dict[int, str] | None = None):
        self.user = user
        self.access = AutomationNodeAccess(user)
        self.refs = refs or {}
        self._workflows: dict[int, tuple[dict, dict]] = {}

    def _read(self, workflow) -> tuple[dict, dict]:
        """
        The node each node of the workflow follows, by node ID, and the example
        data of the nodes that have any.
        """

        if workflow.id not in self._workflows:
            previous_of: dict[int, AutomationNode | None] = {}
            examples = {}
            # All the nodes, also those no path reaches, which nodes can still
            # read.
            workflow_nodes = list(
                AutomationNodeService().get_nodes(self.user, workflow)
            )
            ordered = shared_nodes.nodes_in_order(self.user, workflow, workflow_nodes)
            self.access.add_nodes(workflow_nodes, all_of_workflow=True)
            for node, previous, _output in ordered:
                previous_of[node.id] = previous
                service = node.service.specific
                # As the user may see it.
                schema = visible_schema(service, self.access)
                if not schema:
                    continue
                try:
                    example = create_example_from_json_schema(schema)
                    metadata = minimize_json_schema(schema)
                except ValueError:
                    # Not a schema of objects, such as an iterator over a list
                    # of texts. The node is left out, like one without a schema.
                    continue
                metadata["node_id"] = node.id
                metadata["label"] = node.label
                metadata["node_type"] = node.get_type().type
                metadata["formula_path"] = shared_nodes.formula_path(node)
                if node.id in self.refs:
                    metadata["node_ref"] = self.refs[node.id]
                if previous is not None:
                    metadata["previous_node_id"] = previous.id
                examples[node.id] = (example, metadata)
            self._workflows[workflow.id] = (previous_of, examples)
        return self._workflows[workflow.id]

    def refs_of(self, workflow) -> dict[str, int]:
        """
        The ID of each node of the workflow by the ref it was created under. Refs
        repeat across workflows created in one call, so they are only read within
        one workflow.
        """

        previous_of, _examples = self._read(workflow)
        return {
            ref: node_id for node_id, ref in self.refs.items() if node_id in previous_of
        }

    def previous(self, node: AutomationNode) -> AutomationNode | None:
        """
        The node ``node`` follows, when the generator gets its data. One without
        example data, such as an iterator with no sample, isn't named.
        """

        previous_of, examples = self._read(node.workflow)
        previous = previous_of.get(node.id)
        return previous if previous is not None and previous.id in examples else None

    def context_for(self, node: AutomationNode) -> "AssistantFormulaContext":
        """
        The nodes that run before ``node`` on its path, the only ones its
        formulas can read.
        """

        previous_of, examples = self._read(node.workflow)
        context = AssistantFormulaContext()
        ancestor = previous_of.get(node.id)
        ancestors = []
        while ancestor is not None:
            ancestors.append(ancestor.id)
            ancestor = previous_of.get(ancestor.id)
        for node_id in reversed(ancestors):
            if node_id in examples:
                example, metadata = examples[node_id]
                context.add_node_context(node_id, example, metadata)
        return context
