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
from .types import HasFormulasToCreateMixin, NodeBase, WorkflowCreate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers


class AssistantFormulaContext(BaseFormulaContext):
    """
    Automation-specific formula context with previous_node structure.

    Extends the shared BaseFormulaContext to provide the nested
    {"previous_node": {...}} structure expected by automation formulas.
    """

    def add_node_context(
        self,
        node_id: int | str,
        node_context: dict[str, Any],
        context_metadata: dict[str, dict[str, str]] | None = None,
    ):
        """Update the formula context with new node values."""
        self.add_context(str(node_id), node_context, context_metadata)

    def get_formula_context(self) -> dict[str, Any]:
        """Return context wrapped in previous_node for automation formulas."""
        return {"previous_node": self.context}

    def __getitem__(self, key) -> Any:
        """Resolve paths like 'previous_node.1.0.field_name'."""
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
    Loop over all nodes and verify if they have formulas to update. If so, update the
    formulas in the ORM node service providing the available context up to that node and
    the user request for that node.
    """

    context = AssistantFormulaContext()

    def _get_service_schema(orm_node: AutomationNode):
        return orm_node.service.get_type().generate_schema(orm_node.service.specific)

    def _update_context_with_node_data(
        orm_node: AutomationNode, node_to_create: NodeBase
    ):
        schema = _get_service_schema(orm_node)
        example = create_example_from_json_schema(schema)
        descr = minimize_json_schema(schema)
        descr["node_id"] = orm_node.id
        descr["node_ref"] = node_to_create.ref
        if getattr(node_to_create, "previous_node_ref", None):
            descr["previous_node_ref"] = node_to_create.previous_node_ref
        context.add_node_context(orm_node.id, example, descr)

    # Add the trigger context first
    trigger_node = workflow.trigger
    orm_trigger, __ = node_mapping[trigger_node.ref]
    _update_context_with_node_data(orm_trigger, trigger_node)

    generate_formula_tool = get_generate_formulas_tool()

    def _generate_and_update_node_formulas(
        node: HasFormulasToCreateMixin, orm_node: AutomationNode
    ):
        formulas_to_create = node.get_formulas_to_create(orm_node)
        result = generate_formula_tool(formulas_to_create, context)
        if result:
            node.update_service_with_formulas(orm_node.service, result)

    # Node by node, generate formulas if needed and update the context with the node
    # data, so following nodes can use it.
    for node in workflow.nodes:
        orm_node, __ = node_mapping[node.ref]
        if isinstance(node, HasFormulasToCreateMixin):
            tool_helpers.update_status(
                _("Generating formulas for node '%(label)s'..." % {"label": node.label})
            )
            with transaction.atomic():
                try:
                    _generate_and_update_node_formulas(node, orm_node)
                except Exception as exc:
                    logger.exception(
                        "Failed to generate formulas for node {}: {}", orm_node.id, exc
                    )
        _update_context_with_node_data(orm_node, node)
