from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Tuple

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

import udspy
from loguru import logger
from pydantic import ConfigDict

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.service import AutomationWorkflowService
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
    FormulaContext,
)
from baserow.core.models import Workspace
from baserow.core.service import CoreService
from baserow.core.utils import to_path

from .prompts import GENERATE_FORMULA_PROMPT
from .types import HasFormulasToCreateMixin, NodeBase, WorkflowCreate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


def _minimize_json_schema(schema) -> dict[str, dict[str, str]]:
    """
    Generate a mapping between field ids and names/types from a JSON schema.
    Useful when generating formulas to understand the provided context.
    """

    field_type_descriptions = {
        "link_row": "the row ID as number or the primary field value as string",
        "single_select": "the option ID as number or the value as string",
        "multiple_select": "a comma separated list of option IDs or values as string",
        "date": "a date string in ISO 8601 format",
        "date_time": "a date-time string in ISO 8601 format",
        "boolean": "true or false",
    }
    field_type_extra_info = {
        "single_select": lambda meta: {
            "select_options": meta.get("select_options", [])
        },
        "multiple_select": lambda meta: {
            "select_options": meta.get("select_options", [])
        },
        "multiple_collaborators": lambda meta: {
            "available_collaborators": meta.get("available_collaborators", [])
        },
    }

    if schema.get("type") == "array":
        return _minimize_json_schema(schema.get("items"))
    elif schema.get("type") != "object":
        raise ValueError("Schema must be of type object or array of objects")

    properties = schema.get("properties", {})
    mapping = {}
    for key, prop in properties.items():
        metadata = prop.get("metadata")
        if metadata:
            field_type = metadata["type"]
            mapping[key] = {
                "id": metadata["id"],
                "name": metadata["name"],
                "type": field_type,
                "desc": field_type_descriptions.get(field_type, ""),
            }
            if field_type in field_type_extra_info:
                get_extra_info = field_type_extra_info[field_type]
                mapping[key].update(get_extra_info(metadata))
    return mapping


def _create_example_from_json_schema(schema) -> Tuple[dict, dict]:
    """
    Generate example data from a JSON schema.
    Useful when generating formulas to provide example context data.
    """

    examples = {
        "string": "text",
        "number": 1,
        "boolean": True,
        "null": None,
        "object": lambda prop: _create_example_from_json_schema(prop),
        "array": lambda prop: [_create_example_from_json_schema(prop["items"])],
    }

    if schema.get("type") == "array":
        return [_create_example_from_json_schema(schema.get("items"))]
    elif schema.get("type") != "object":
        raise ValueError("Schema must be of type object or array of objects")

    properties = schema.get("properties", {})
    example = {}
    for key, prop in properties.items():
        value = examples[prop.get("type")]
        if callable(value):
            example[key] = value(prop)
        else:
            example[key] = value
    return example


class AssistantFormulaContext(FormulaContext):
    def __init__(self):
        self.context = {}
        self.context_metadata = {}
        super().__init__()

    def add_node_context(
        self,
        node_id: int | str,
        node_context: dict[str, any],
        context_metadata: dict[str, dict[str, str]] | None = None,
    ):
        """Update the formula context with new values."""

        self.context.update({str(node_id): node_context})
        if context_metadata:
            self.context_metadata.update({str(node_id): context_metadata})

    def get_formula_context(self) -> dict[str, any]:
        return {"previous_node": self.context}

    def get_context_metadata(self) -> dict[str, any]:
        return self.context_metadata

    def __getitem__(self, key) -> any:
        start, *key_parts = to_path(key)
        if start != "previous_node":
            raise KeyError(
                f"Key '{key}' not found in context. Only 'previous_node' is supported at the root level."
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
                    f"Key '{kp}' of '{key}' not found in {value}, Available keys: {available_keys}"
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
    class RuntimeFormulaGenerator(udspy.Signature):
        __doc__ = GENERATE_FORMULA_PROMPT

        fields_to_resolve: dict[str, dict[str, str]] = udspy.InputField(
            desc=(
                "The fields that need formulas to be generated. "
                "If prefixed with [optional], the field is not mandatory."
            )
        )
        context: dict[str, Any] = udspy.InputField(
            desc="The available context to use in formula generation composed of previous nodes results."
        )
        context_metadata: dict[str, Any] = udspy.InputField(
            desc="Metadata about the context fields, with refs and names to assist in formula generation."
        )
        feedback: str = udspy.InputField(
            desc="Validation errors from previous attempt. Empty if first attempt."
        )
        generated_formulas: dict[str, Any] = udspy.OutputField()

        model_config = ConfigDict(arbitrary_types_allowed=True)

    def check_formula(generated_formula: str, context: AssistantFormulaContext) -> str:
        try:
            resolve_formula(
                BaserowFormulaObject.create(
                    formula=generated_formula, mode=BASEROW_FORMULA_MODE_ADVANCED
                ),
                formula_runtime_function_registry,
                context,
            )
        except Exception as exc:
            raise ValueError(f"Generated formula is invalid: {str(exc)}")
        return "ok, the formula is valid"

    def generate_node_formulas(
        fields_to_resolve: dict,
        context: AssistantFormulaContext,
        max_retries: int = 3,
    ) -> str:
        """
        For every non-null input field in the node's schema, generate a formula
        that fulfills the request, using the provided context object.
        """

        predict = udspy.Predict(RuntimeFormulaGenerator)
        feedback = ""
        for __ in range(max_retries):
            result = predict(
                fields_to_resolve=fields_to_resolve,
                context=context.get_formula_context(),
                context_metadata=context.get_context_metadata(),
                feedback=feedback,
            )
            # Ensure all the generated formulas are valid
            valid_formulas = {}
            generated_formulas = result.generated_formulas
            for field_id, formula in generated_formulas.items():
                try:
                    check_formula(formula, context)
                    valid_formulas[field_id] = formula
                except ValueError as exc:
                    feedback += f"Error for {field_id}, formula {formula} not valid: {str(exc)}\n"

            if len(valid_formulas) == len(generated_formulas):
                return valid_formulas

        # Any valid formula is better than none
        if valid_formulas:
            return valid_formulas
        else:
            raise ValueError(
                "Failed to generate any valid formulas after "
                f"{max_retries} attempts. Feedback:\n{feedback}"
            )

    return generate_node_formulas


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
        example = _create_example_from_json_schema(schema)
        descr = _minimize_json_schema(schema)
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
