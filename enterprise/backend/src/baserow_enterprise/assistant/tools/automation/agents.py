"""
Sub-agents for the automation assistant tools.

Contains:
- ``AssistantFormulaContext``: Automation-specific formula context.
- ``get_generate_formulas_tool()``: Gets the automation formula generator.
- ``update_workflow_formulas()``: Generates formulas for workflow nodes.
"""

from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils.translation import gettext as _

from loguru import logger

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow_enterprise.assistant.tools.shared.agents import get_formula_generator
from baserow_enterprise.assistant.tools.shared.formula_utils import (
    BaseFormulaContext,
    create_example_from_json_schema,
    minimize_json_schema,
)

from .prompts import GENERATE_FORMULA_PROMPT
from .types import ActionNodeCreate, NodeUpdate, WorkflowCreate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers


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


def get_generate_formulas_tool():
    """Get the automation formula generator using the shared factory."""
    return get_formula_generator(GENERATE_FORMULA_PROMPT)


def update_workflow_formulas(
    workflow: "WorkflowCreate",
    node_mapping: dict[int | str, Any],
    tool_helpers: "ToolHelpers",
) -> None:
    """
    Generate and apply formulas for all nodes in a newly created workflow.

    Walks nodes in order, building up the available formula context as it goes.
    For each node that has ``$formula:`` values, delegates to the formula
    generation agent and writes the results back to the ORM service.
    """

    context = AssistantFormulaContext()
    generate_formula = get_generate_formulas_tool()

    def _build_node_context(orm_node: AutomationNode, node_create):
        """Extract schema/example from a node and add it to the formula context."""

        schema = orm_node.service.get_type().generate_schema(orm_node.service.specific)
        example = create_example_from_json_schema(schema)
        metadata = minimize_json_schema(schema)
        metadata["node_id"] = orm_node.id
        metadata["node_ref"] = node_create.ref
        if getattr(node_create, "previous_node_ref", None):
            metadata["previous_node_ref"] = node_create.previous_node_ref
        context.add_node_context(orm_node.id, example, metadata)

    def _generate_node_formulas(node: ActionNodeCreate, orm_node: AutomationNode):
        """Generate formulas for a single node and write them to the service."""

        formulas_to_create = node.get_formulas_to_create(orm_node)
        if formulas_to_create is None:
            return
        result = generate_formula(formulas_to_create, context)
        if result:
            node.update_service_with_formulas(orm_node.service, result)

    # Seed context with the trigger
    orm_trigger, trigger_create = node_mapping[workflow.trigger.ref]
    _build_node_context(orm_trigger, trigger_create)

    # Process action nodes in order
    for node in workflow.nodes:
        orm_node, _node_create = node_mapping[node.ref]
        node.apply_direct_values(orm_node.service)

        if node.get_formulas_to_create(orm_node) is not None:
            tool_helpers.update_status(
                _("Generating formulas for node '%(label)s'..." % {"label": node.label})
            )
            with transaction.atomic():
                try:
                    _generate_node_formulas(node, orm_node)
                except Exception as exc:
                    logger.exception(
                        "Failed to generate formulas for node {}: {}", orm_node.id, exc
                    )

        _build_node_context(orm_node, node)


def update_single_node_formulas(
    node_update: "NodeUpdate",
    orm_node: AutomationNode,
    tool_helpers: "ToolHelpers",
) -> None:
    """
    Generate and apply formulas for a single node being updated.

    Builds formula context from the node's workflow, then generates
    formulas for the $formula: fields in the update.
    """

    context = AssistantFormulaContext()
    generate_formula = get_generate_formulas_tool()

    # Build context from the workflow's existing nodes
    workflow = orm_node.workflow
    all_nodes = list(workflow.automation_workflow_nodes.all().order_by("id"))
    for wf_node in all_nodes:
        schema = wf_node.service.get_type().generate_schema(wf_node.service.specific)
        example = create_example_from_json_schema(schema)
        metadata = minimize_json_schema(schema)
        metadata["node_id"] = wf_node.id
        context.add_node_context(wf_node.id, example, metadata)

    formulas_to_create = node_update.get_formulas_to_update(orm_node)
    if formulas_to_create is None:
        return

    result = generate_formula(formulas_to_create, context)
    if result:
        node_update.update_service_with_formulas(orm_node.service, result)
