from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Tuple

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

from loguru import logger

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow.core.utils import to_path
from baserow_enterprise.assistant.tools.shared.formula_utils import (
    BaseFormulaContext,
    create_example_from_json_schema,
    get_formula_generator,
    minimize_json_schema,
)

from .prompts import GENERATE_FORMULA_PROMPT
from .types import HasFormulasToCreateMixin, NodeBase, WorkflowCreate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


class AssistantFormulaContext(BaseFormulaContext):
    """
    Automation-specific formula context with previous_node structure.

    Extends the shared BaseFormulaContext to provide the nested
    {"previous_node": {...}} structure expected by automation formulas.
    """

    def add_node_context(
        self,
        node_id: int | str,
        node_context: dict[str, any],
        context_metadata: dict[str, dict[str, str]] | None = None,
    ):
        """Update the formula context with new node values."""
        self.add_context(str(node_id), node_context, context_metadata)

    def get_formula_context(self) -> dict[str, any]:
        """Return context wrapped in previous_node for automation formulas."""
        return {"previous_node": self.context}

    def __getitem__(self, key) -> any:
        """Resolve paths like 'previous_node.1.0.field_name'."""
        start, *key_parts = to_path(key)
        if start != "previous_node":
            raise KeyError(
                f"Key '{key}' not found in context. "
                "Only 'previous_node' is supported at the root level."
            )
        value = self.context
        for kp in key_parts:
            try:
                value = value[int(kp) if isinstance(value, list) else kp]
            except (KeyError, TypeError, ValueError):
                available_keys = (
                    list(value.keys())
                    if isinstance(value, dict)
                    else ", ".join(map(str, range(len(value))))
                )
                raise KeyError(
                    f"Key '{kp}' of '{key}' not found in {value}, "
                    f"Available keys: {available_keys}"
                )
        if not isinstance(value, (int, float, str, bool, date, datetime)):
            raise ValueError(
                f"Value for key '{key}' is not a valid type. "
                f"Expected int, float, str, bool, date, or datetime. "
                f"Got {type(value).__name__} instead. "
                f"Make sure to only reference primitive types in the formula context."
            )
        return value


def get_generate_formulas_tool():
    """Get the automation formula generator using the shared factory."""
    return get_formula_generator(GENERATE_FORMULA_PROMPT)


def get_automation(
    automation_id: int, user: AbstractUser, workspace: Workspace
) -> Automation:
    """Get automation with permission check."""

    base_queryset = Automation.objects.filter(workspace=workspace)
    automation = CoreService().get_application(
        user, automation_id, base_queryset=base_queryset
    )
    return automation


def get_workflow(
    workflow_id: int, user: AbstractUser, workspace: Workspace
) -> AutomationWorkflow:
    """Get workflow with permission check."""

    workflow = AutomationWorkflowService().get_workflow(user, workflow_id)
    if workflow.automation.workspace_id != workspace.id:
        raise ValueError("Workflow not in workspace")
    return workflow


def create_workflow(
    user: AbstractUser,
    automation: Automation,
    workflow: "WorkflowCreate",
    tool_helpers: "ToolHelpers",
) -> Tuple[AutomationWorkflow, dict[int | str, Any]]:
    """
    Creates a new workflow in the given automation based on the provided definition.
    """

    tool_helpers.update_status(
        _("Creating workflow '%(name)s'..." % {"name": workflow.name})
    )

    orm_wf = AutomationWorkflowService().create_workflow(
        user, automation.id, workflow.name
    )

    node_mapping = {}

    # First create the trigger node
    orm_service_data = workflow.trigger.to_orm_service_dict()
    node_type = automation_node_type_registry.get(workflow.trigger.type)
    tool_helpers.update_status(
        _("Creating trigger '%(label)s'..." % {"label": workflow.trigger.label})
    )
    orm_trigger = AutomationNodeService().create_node(
        user,
        node_type,
        orm_wf,
        label=workflow.trigger.label,
        service=orm_service_data,
    )

    node_mapping[workflow.trigger.ref] = node_mapping[orm_trigger.id] = (
        orm_trigger,
        workflow.trigger,
    )

    for node in workflow.nodes:
        orm_service_data = node.to_orm_service_dict()
        reference_node_id, output = node.to_orm_reference_node(node_mapping)
        node_type = automation_node_type_registry.get(node.type)
        tool_helpers.update_status(
            _("Creating node '%(label)s'..." % {"label": node.label})
        )
        orm_node = AutomationNodeService().create_node(
            user,
            node_type,
            orm_wf,
            reference_node_id=reference_node_id,
            output=output,
            label=node.label,
            service=orm_service_data,
        )
        node_mapping[node.ref] = node_mapping[orm_node.id] = (orm_node, node)

    return orm_wf, node_mapping


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
                        "Failed to generate formulas for node %s: %s", orm_node.id, exc
                    )
        _update_context_with_node_data(orm_node, node)
